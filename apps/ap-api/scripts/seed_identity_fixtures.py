#!/usr/bin/env python
"""Development-only fictional organization for scoped-authorization tests and the owner's demo dataset (E3:D3.15, D3.17).

Owner rule (E3:D3.19): every record this seed creates is labelled TEMPORARY / TEST DATA (visible name/title prefix and, where the model has a
notes/description field, a "data_class: TEMPORARY_TEST_DATA" marker). Re-running refreshes the labels of an older unlabelled seed.
The role codes start with "fixture." and are ignored by authorization scope resolution when ASAA_AP_ENVIRONMENT is production.

Creates, idempotently: organization profile, units/departments, about ten fictional people (example.invalid emails) with employment
records and manager links, a payroll run with fictional entries, customers with invoices, suppliers, two engagements with a milestone and
work orders, one active role template per scope type and approved assignments with mixed scopes. Nothing here is real personal data.

  DEMO_ORG_ID=asaa python scripts/seed_identity_fixtures.py          (also runs scripts/seed_demo_workspace.py; DEMO_ORG_ID unset: defaults to "asaa", the realm's org_id claim)
  DEMO_USER_EMAIL=<owner email> DEMO_USER_SUBJECT=<token sub> python scripts/seed_identity_fixtures.py

DEMO_USER_EMAIL / DEMO_USER_SUBJECT are read from the environment only (never committed): the HR record is matched by work email and
linked to that login subject. No password is ever stored. Refuses to run unless ASAA_AP_ENVIRONMENT is development or test.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

DEFAULT_DEMO_ORG = "asaa"
SEED_ACTOR = "seed:fixtures"
REVIEWER = "seed:reviewer"
EXAMPLE_DOMAIN = "example.invalid"
TEST_LABEL = "TEMPORARY / TEST DATA"
TEST_PREFIX = f"{TEST_LABEL} – "
DATA_CLASS_MARKER = "data_class: TEMPORARY_TEST_DATA"

FIXTURE_PERMISSIONS = [
    "hr:employee:read", "hr:employee:write", "hr:employment:write", "payroll:read", "payroll:entry:write",
    "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:receipt:read", "ar:receipt:write",
    "delivery:engagement:read", "delivery:engagement:write", "delivery:engagement:manage", "delivery:workorder:read", "delivery:workorder:write",
    "delivery:workorder:assign", "delivery:milestone:deliver", "delivery:milestone:accept",
]
ROLE_SCOPES = {  # scope type -> role code
    "Organization": "fixture.org.admin", "Unit": "fixture.unit.lead", "Department": "fixture.department.officer",
    "Project": "fixture.project.lead", "Customer": "fixture.customer.manager", "Record": "fixture.record.reader",
}

UNITS = [  # code, type, name, parent code
    ("EXH", "Legal Entity", "Example Holdings (fictional)", None),
    ("OPS", "Division", "Operations", "EXH"),
    ("ENG", "Department", "Engineering", "OPS"),
    ("PLT", "Team", "Platform Team", "ENG"),
    ("FIN", "Department", "Finance", "EXH"),
    ("PPL", "Department", "People", "EXH"),
]
PEOPLE = [  # code, first, last, unit code, title, manager code
    ("FX-001", "Avery", "Example", "EXH", "Chief Executive (fictional)", None),
    ("FX-002", "Blake", "Sample", "ENG", "Engineering Lead", "FX-001"),
    ("FX-003", "Casey", "Placeholder", "PLT", "Platform Engineer", "FX-002"),
    ("FX-004", "Drew", "Fictional", "PLT", "Platform Engineer", "FX-002"),
    ("FX-005", "Emery", "Testperson", "FIN", "Finance Manager", "FX-001"),
    ("FX-006", "Finley", "Mockson", "FIN", "Accounts Officer", "FX-005"),
    ("FX-007", "Gray", "Dummy", "PPL", "People Partner", "FX-001"),
    ("FX-008", "Harper", "Notreal", "PPL", "Recruiter", "FX-007"),
    ("FX-009", "Indigo", "Samplesmith", "ENG", "Delivery Analyst", "FX-002"),
    ("FX-010", "Jules", "Faux", "FIN", "Payroll Clerk", "FX-005"),
]
CUSTOMERS = [("FXC-001", "Northwind Example Ltd"), ("FXC-002", "Contoso Sample Inc"), ("FXC-003", "Fabrikam Placeholder LLC")]
SUPPLIERS = [("FXS-001", "Acme Fictional Supplies"), ("FXS-002", "Globex Example Services")]


def refuse_unless_dev(settings) -> None:
    if settings.environment not in {"development", "test"}:
        raise SystemExit(f"Refusing to seed fictional data: ASAA_AP_ENVIRONMENT is {settings.environment!r} (only development or test).")


def label(text: str, limit: int | None = None) -> str:
    """Prefix `text` with the TEMPORARY / TEST DATA label (once), cut to the column length `limit` (the label itself is always kept)."""
    out = text if text.startswith(TEST_PREFIX) else TEST_PREFIX + text
    return out[:limit] if limit else out


def marked(note: str = "") -> str:
    """A notes/description value carrying the data_class marker (idempotent)."""
    return f"{DATA_CLASS_MARKER}. {note}".strip() if note else DATA_CLASS_MARKER


def _get_or_create(db, model, where: dict, create: dict, refresh: dict | None = None):
    """Match by the stable identifiers in `where`; `refresh` values (labels) are also applied to an already existing row."""
    row = db.scalar(select(model).filter_by(**where))
    if row is None:
        row = model(**where, **create, **(refresh or {}))
        db.add(row)
        db.flush()
    else:
        for key, value in (refresh or {}).items():
            if getattr(row, key) != value:
                setattr(row, key, value)
        db.flush()
    return row


def seed_fixtures(db, org_id: str, owner_email: str | None = None, owner_subject: str | None = None) -> dict:
    from asaa_ap.models import ARCustomer, ARInvoice, Supplier
    from asaa_delivery.models import Engagement, Milestone, WorkOrder
    from asaa_governance.administration import OrganizationProfile, OrganizationUnit
    from asaa_governance.authorization import AuthorizationAssignment, AuthorizationRoleTemplate
    from asaa_identity.models import IdentitySubjectLink
    from asaa_people.models import Employee, EmploymentRecord, PayrollEntry, PayrollPeriod, PayrollRun

    now = datetime.now(timezone.utc)
    today = date.today()
    out: dict = {"org": org_id, "units": {}, "employees": {}, "customers": {}, "invoices": {}, "engagements": {}, "roles": {}, "assignments": {}}

    _get_or_create(db, OrganizationProfile, {"organization_id": org_id}, {"lifecycle_status": "Active", "country_code": "ZZ", "updated_by": SEED_ACTOR},
                  {"display_name": label("Example Holdings (fictional demo)", 200)})
    for code, unit_type, name, parent in UNITS:
        unit = _get_or_create(db, OrganizationUnit, {"organization_id": org_id, "unit_code": code},
                              {"unit_type": unit_type, "parent_id": out["units"][parent] if parent else None, "status": "Active",
                               "created_by": SEED_ACTOR, "updated_by": SEED_ACTOR, "reviewed_by": REVIEWER, "reviewed_at": now, "effective_from": today},
                              {"name": label(name, 180), "description": marked()})
        out["units"][code] = unit.id

    for code, first, last, unit_code, title, manager in PEOPLE:
        email = f"{first}.{last}@{EXAMPLE_DOMAIN}".lower()
        emp = _get_or_create(db, Employee, {"organization_id": org_id, "employee_code": code},
                             {"first_name": first, "last_name": last, "work_email": email, "employment_type": "Employee", "status": "Active",
                              "hire_date": today - timedelta(days=400), "created_by": SEED_ACTOR},
                             {"preferred_name": label(f"{first} {last}", 120)})
        out["employees"][code] = emp.id
        if db.scalar(select(EmploymentRecord.id).where(EmploymentRecord.organization_id == org_id, EmploymentRecord.employee_id == emp.id)) is None:
            db.add(EmploymentRecord(organization_id=org_id, employee_id=emp.id, department_id=out["units"][unit_code], position_title=title,
                                    manager_employee_id=out["employees"][manager] if manager else None, employment_type="Employee", status="Active",
                                    effective_from=today - timedelta(days=365), created_by=SEED_ACTOR))
    db.flush()

    if owner_email:  # the owner's own login: matched by work email in the HR record only; a password is never stored
        owner = db.scalar(select(Employee).where(Employee.organization_id == org_id, Employee.work_email == owner_email))
        if owner is None:
            owner = _get_or_create(db, Employee, {"organization_id": org_id, "employee_code": "FX-OWNER"},
                                   {"first_name": "Demo", "last_name": "Owner", "work_email": owner_email, "employment_type": "Employee", "status": "Active",
                                    "hire_date": today - timedelta(days=30), "created_by": SEED_ACTOR},
                                   {"preferred_name": label("Demo Owner", 120)})
        out["employees"]["owner"] = owner.id
        if owner_subject:
            link = db.scalar(select(IdentitySubjectLink).where(IdentitySubjectLink.organization_id == org_id, IdentitySubjectLink.employee_id == owner.id))
            if link is None:
                db.add(IdentitySubjectLink(organization_id=org_id, employee_id=owner.id, subject=owner_subject, created_by=SEED_ACTOR))

    period = _get_or_create(db, PayrollPeriod, {"organization_id": org_id, "period_code": "FX-PERIOD-1"},
                            {"start_date": today.replace(day=1), "end_date": today.replace(day=1) + timedelta(days=27), "status": "Open", "created_by": SEED_ACTOR})
    run = _get_or_create(db, PayrollRun, {"organization_id": org_id, "run_code": "FX-RUN-1"},
                         {"period_id": period.id, "status": "Draft", "currency": "USD", "created_by": SEED_ACTOR})
    out["payroll_run"] = run.id
    out["payroll_entries"] = {}
    for code, *_ in PEOPLE:
        entry = _get_or_create(db, PayrollEntry, {"organization_id": org_id, "run_id": run.id, "employee_id": out["employees"][code]},
                               {"currency": "USD", "gross_amount": Decimal("1000.00"), "deduction_total": Decimal("100.00"),
                                "net_amount": Decimal("900.00"), "breakdown": {}, "status": "Draft", "created_by": SEED_ACTOR})
        out["payroll_entries"][code] = entry.id

    for code, name in CUSTOMERS:
        customer = _get_or_create(db, ARCustomer, {"organization_id": org_id, "customer_code": code},
                                  {"email": f"accounts@{code.lower()}.{EXAMPLE_DOMAIN}", "status": "Active", "created_by": SEED_ACTOR},
                                  {"legal_name": label(name, 240)})
        out["customers"][code] = customer.id
        invoice = _get_or_create(db, ARInvoice, {"organization_id": org_id, "invoice_number": f"FX-INV-{code[-3:]}"},
                                 {"customer_id": customer.id, "currency": "USD", "issue_date": today, "due_date": today + timedelta(days=30), "status": "Issued",
                                  "subtotal": Decimal("500.00"), "tax_total": Decimal("0.00"), "total": Decimal("500.00"), "created_by": SEED_ACTOR},
                                 {"notes": marked()})
        out["invoices"][code] = invoice.id
    for code, name in SUPPLIERS:
        _get_or_create(db, Supplier, {"organization_id": org_id, "supplier_code": code},
                       {"email": f"ap@{code.lower()}.{EXAMPLE_DOMAIN}", "normalized_email": f"ap@{code.lower()}.{EXAMPLE_DOMAIN}", "status": "Active",
                        "created_by": SEED_ACTOR, "updated_by": SEED_ACTOR},
                       {"legal_name": label(name, 240), "normalized_legal_name": " ".join(label(name, 240).casefold().split()), "notes": marked()})

    for index, (code, ccode) in enumerate((("FX-ENG-1", "FXC-001"), ("FX-ENG-2", "FXC-002")), start=1):
        engagement = _get_or_create(db, Engagement, {"organization_id": org_id, "code": code},
                                    {"customer_id": out["customers"][ccode], "project_reference": f"FX-PROJECT-{index}",
                                     "owner_subject": "fx-project-lead", "start_date": today, "currency": "USD", "status": "Active", "created_by": SEED_ACTOR},
                                    {"title": label(f"Fictional engagement {index}", 200)})
        out["engagements"][code] = engagement.id
        milestone = db.scalar(select(Milestone).where(Milestone.engagement_id == engagement.id).order_by(Milestone.id))
        if milestone is None:
            db.add(Milestone(organization_id=org_id, engagement_id=engagement.id, title=label(f"Milestone {index}", 200), deliverable=marked(),
                             due_date=today + timedelta(days=30), status="Planned", created_by=SEED_ACTOR))
        else:  # an older unlabelled seed: relabel the seed's own (first) milestone
            milestone.title, milestone.deliverable = label(milestone.title, 200), milestone.deliverable or marked()
        work_order = db.scalar(select(WorkOrder).where(WorkOrder.engagement_id == engagement.id).order_by(WorkOrder.id))
        if work_order is None:
            db.add(WorkOrder(organization_id=org_id, engagement_id=engagement.id, title=label(f"Work order {index}", 200), description=marked(),
                             status="Open", created_by=SEED_ACTOR))
        else:
            work_order.title, work_order.description = label(work_order.title, 200), work_order.description or marked()
    db.flush()

    for scope_type, role_code in ROLE_SCOPES.items():
        role = _get_or_create(db, AuthorizationRoleTemplate, {"organization_id": org_id, "role_code": role_code},
                              {"scope_type": scope_type, "permissions": FIXTURE_PERMISSIONS, "status": "Active",
                               "created_by": SEED_ACTOR, "reviewed_by": REVIEWER, "reviewed_at": now, "review_reason": "Fictional fixture"},
                              {"name": label(f"{scope_type} scope fixture role", 160),
                               "description": marked("Fixture role; ignored by authorization in production.")})
        out["roles"][scope_type] = role.id
    mixed = [  # subject, scope type, scope reference
        ("fx-org-admin", "Organization", f"organization:{org_id}"),
        ("fx-unit-lead", "Unit", f"unit:{out['units']['OPS']}"),
        ("fx-department-officer", "Department", f"department:{out['units']['FIN']}"),
        ("fx-project-lead", "Project", "project:FX-PROJECT-1"),
        ("fx-customer-manager", "Customer", f"customer:{out['customers']['FXC-001']}"),
        ("fx-record-reader", "Record", f"record:{out['invoices']['FXC-002']}"),
    ]
    for subject, scope_type, reference in mixed:
        assignment = _get_or_create(db, AuthorizationAssignment, {"organization_id": org_id, "role_template_id": out["roles"][scope_type], "subject": subject,
                                                                  "scope_reference": reference},
                                    {"effective_from": now - timedelta(days=1), "reason": "Fictional fixture assignment", "status": "Approved",
                                     "created_by": SEED_ACTOR, "reviewed_by": REVIEWER, "reviewed_at": now, "review_reason": "Fictional fixture"})
        out["assignments"][subject] = assignment.id
    db.commit()
    return out


def main() -> int:
    from asaa_ap.config import get_settings
    settings = get_settings()
    refuse_unless_dev(settings)
    org_id = os.environ.get("DEMO_ORG_ID", "").strip()
    if not org_id:
        org_id = DEFAULT_DEMO_ORG
        print(f"DEMO_ORG_ID is not set: defaulting to {org_id!r} (the org_id claim of every local Keycloak token). Set DEMO_ORG_ID=<id> to use another organization.")
    owner_email = os.environ.get("DEMO_USER_EMAIL", "").strip() or None
    owner_subject = os.environ.get("DEMO_USER_SUBJECT", "").strip() or None
    if owner_email and not owner_subject:
        print("DEMO_USER_EMAIL is set without DEMO_USER_SUBJECT: the HR record is created/matched but not linked to a login subject.")
    from asaa_ap.database import Base, SessionLocal, engine
    import asaa_ap.main  # noqa: F401  (registers every model on Base)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        result = seed_fixtures(db, org_id, owner_email, owner_subject)
        import seed_demo_workspace  # same directory (E3:D3.23): demo records for the remaining workspaces
        demo = seed_demo_workspace.seed_demo(db, org_id, result, owner_subject)
    print(f"Seeded fictional organization {org_id!r}: {len(result['employees'])} people, {len(result['customers'])} customers, "
          f"{len(result['units'])} units, {len(result['assignments'])} approved assignments; demo workspace: {sum(demo.values())} rows across {len(demo)} tables. Safe to re-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
