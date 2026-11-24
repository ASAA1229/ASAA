#!/usr/bin/env python
"""Development-only fictional demo records for every portal workspace that the identity seed leaves empty (E3:D3.23).

Run AFTER seed_identity_fixtures (it links to that seed's employees, units, customers, suppliers and engagements):

  python scripts/seed_identity_fixtures.py        (calls this seed at its end, so one command seeds everything)
  python scripts/seed_demo_workspace.py           (stand-alone; seeds the base fixtures first if they are missing)

Same conventions as seed_identity_fixtures: refuses unless ASAA_AP_ENVIRONMENT is development or test, org defaults to "asaa" (DEMO_ORG_ID
overrides), emails use example.invalid, every record is labelled TEMPORARY / TEST DATA (title/name prefix, or a data_class marker in a notes
field), and everything is idempotent (matched by stable business keys; re-running creates nothing new). Nothing here is real personal data.

Records are written through the ORM models in states the application's own workflows can reach (maker is never the reviewer; approved
records carry a reviewer; derived balances such as invoice status are kept consistent with allocations and credits).
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))
sys.path.insert(0, str(_HERE))

from seed_identity_fixtures import (  # noqa: E402
    DEFAULT_DEMO_ORG, EXAMPLE_DOMAIN, PEOPLE, REVIEWER, SEED_ACTOR, _get_or_create, label, marked, refuse_unless_dev, seed_fixtures,
)

D = Decimal


def _subject(code: str) -> str:
    return f"fx-emp-{code[-3:]}"


def _count(db, model, org_id: str) -> int:
    from sqlalchemy import func
    col = getattr(model, "organization_id", None)
    stmt = select(func.count()).select_from(model)
    return db.scalar(stmt.where(col == org_id) if col is not None else stmt) or 0


# --------------------------------------------------------------------------------------------------------------- governed registers
def _register_samples(today: date) -> dict[str, list[tuple[str, str, dict, str]]]:
    """register_type -> [(code, title, data, status)]. Data is validated against the register catalogue before writing."""
    year, quarter = today.year, (today.month - 1) // 3 + 1
    d = lambda n: (today + timedelta(days=n)).isoformat()  # noqa: E731
    A, R, W = "Approved", "In Review", "Draft"
    return {
        "policy": [("POL-001", "Acceptable use policy", {"document_type": "Policy", "scope": "All staff", "acknowledgement_required": True}, A),
                   ("POL-002", "Expense approval procedure", {"document_type": "Procedure", "scope": "Finance", "acknowledgement_required": False}, R)],
        "risk": [("RSK-001", "Key supplier concentration", {"category": "Supply", "likelihood": "Medium", "impact": "High", "mitigation": "Qualify a second supplier"}, A),
                 ("RSK-002", "Single approver for payments", {"category": "Finance", "likelihood": "Low", "impact": "High", "mitigation": "Maker-checker enforced"}, A)],
        "control": [("CTL-001", "Monthly access review", {"control_type": "Detective", "frequency": "Monthly", "related_risk_code": "RSK-002"}, A),
                    ("CTL-002", "Payment batch dual approval", {"control_type": "Preventive", "frequency": "Continuous", "related_risk_code": "RSK-002"}, A)],
        "obligation": [("OBL-001", "Annual records review", {"source": "Internal standard (fictional)", "evidence_reference": "demo/evidence/records-review"}, A),
                       ("OBL-002", "Supplier due-diligence refresh", {"source": "Contract template (fictional)"}, W)],
        "contract": [("CON-001", "Northwind master services agreement", {"counterparty": "Northwind Example Ltd", "contract_type": "Customer", "renewal_date": d(120), "auto_renew": True}, A),
                     ("CON-002", "Acme supply agreement", {"counterparty": "Acme Fictional Supplies", "contract_type": "Supplier", "renewal_date": d(200), "auto_renew": False}, A)],
        "retention_rule": [("RET-001", "Expense receipts", {"data_category": "Expense receipts", "retention_period_months": 84, "disposal_method": "Delete"}, A),
                           ("RET-002", "Recruitment records", {"data_category": "Candidate data", "retention_period_months": 12, "disposal_method": "Anonymise"}, R)],
        "article": [("KB-001", "How to submit an expense claim", {"space": "Finance", "tags": "expenses,howto"}, A),
                    ("KB-002", "Requesting leave", {"space": "People", "tags": "leave,howto"}, A)],
        "announcement": [("ANN-001", "Welcome to the demo workspace", {"audience": "All staff", "publish_on": d(0)}, A),
                         ("ANN-002", "Quarterly planning week", {"audience": "Managers", "publish_on": d(14)}, W)],
        "integration": [("INT-001", "Identity provider (fictional)", {"kind": "Identity", "credential_reference": "secrets/demo/idp", "health_status": "Healthy", "last_sync_note": "Demo sync ok"}, A),
                        ("INT-002", "Payroll export (fictional)", {"kind": "Payroll", "credential_reference": "secrets/demo/payroll", "health_status": "Unknown"}, W)],
        "workflow_definition": [("WFD-001", "Purchase request approval", {"initial_state": "Draft", "states": ["Draft", "Submitted", "Approved", "Rejected"],
                                 "transitions": [{"from": "Draft", "to": "Submitted", "action": "submit"}, {"from": "Submitted", "to": "Approved", "action": "approve", "permission": "procurement:request:review"},
                                                 {"from": "Submitted", "to": "Rejected", "action": "reject"}]}, A)],
        "security_incident": [("SEC-001", "Phishing report (drill)", {"severity": "Low", "detected_on": d(-20), "containment": "Mailbox rule removed"}, A),
                              ("SEC-002", "Unused admin account found", {"severity": "Medium", "detected_on": d(-6), "containment": "Account disabled"}, R)],
        "operational_incident": [("OPI-001", "Report export slow", {"severity": "Low", "service": "Reports", "detected_on": d(-9)}, A),
                                 ("OPI-002", "Notification delay", {"severity": "Medium", "service": "Notifications", "detected_on": d(-3)}, R)],
        "document": [("DOC-001", "Employee handbook (sample)", {"document_type": "Handbook", "classification": "Internal", "storage_reference": "demo/docs/handbook", "legal_hold": False}, A),
                     ("DOC-002", "Supplier onboarding pack", {"document_type": "Pack", "classification": "Confidential", "storage_reference": "demo/docs/supplier-pack", "retention_until": d(900), "legal_hold": False}, A)],
        "project": [("PRJ-001", "Customer portal refresh", {"project_status": "Active", "sponsor": "Avery Example", "start_date": d(-60), "end_date": d(120), "classification": "Professional"}, A),
                    ("PRJ-002", "Data warehouse pilot", {"project_status": "Planned", "sponsor": "Emery Testperson", "start_date": d(30)}, A)],
        "requirement": [("REQ-001", "Export invoices to CSV", {"priority": "P1", "acceptance_criteria": "CSV matches the on-screen list", "target_release": "R2"}, A),
                        ("REQ-002", "Two-step approval for payments", {"priority": "P0", "acceptance_criteria": "Maker cannot approve", "target_release": "R1"}, A)],
        "product": [("PRD-001", "Client portal", {"lifecycle_stage": "Live", "product_owner": "Blake Sample"}, A),
                    ("PRD-002", "Reporting add-on", {"lifecycle_stage": "Build", "product_owner": "Indigo Samplesmith"}, A)],
        "repository": [("REPO-001", "portal-web", {"host": "git.example.invalid", "default_branch": "main", "owning_team": "Platform Team"}, A),
                       ("REPO-002", "portal-api", {"host": "git.example.invalid", "default_branch": "main", "owning_team": "Platform Team"}, A)],
        "test_plan": [("TP-001", "Regression suite", {"scope": "Portal regression", "last_run_result": "Passed"}, A),
                      ("TP-002", "Payments smoke", {"scope": "AP payments", "last_run_result": "Not run"}, W)],
        "pipeline": [("PIPE-001", "Web build", {"system": "Demo CI", "last_status": "Passing"}, A),
                     ("PIPE-002", "API build", {"system": "Demo CI", "last_status": "Passing"}, A)],
        "environment": [("ENV-001", "Development", {"kind": "Development", "hosting_reference": "local"}, A),
                        ("ENV-002", "Staging", {"kind": "Staging", "hosting_reference": "demo-staging"}, A)],
        "release": [("REL-001", "Release 0.1", {"version_label": "0.1.0", "commit_reference": "demo-commit-0001", "release_status": "Released"}, A),
                    ("REL-002", "Release 0.2", {"version_label": "0.2.0", "release_status": "Planned"}, W)],
        "technical_article": [("TA-001", "Local development setup", {"component": "Platform", "tags": "setup,dev"}, A),
                              ("TA-002", "Database migrations", {"component": "API", "tags": "alembic"}, A)],
        "service": [("SVC-001", "Managed reporting", {"service_owner": "Blake Sample", "support_hours": "Weekdays 09:00-17:00"}, A),
                    ("SVC-002", "Implementation support", {"service_owner": "Indigo Samplesmith", "support_hours": "Business hours"}, A)],
        "engagement": [("ENG-REG-001", "Northwind implementation", {"client": "Northwind Example Ltd", "engagement_status": "Active"}, A),
                       ("ENG-REG-002", "Contoso advisory", {"client": "Contoso Sample Inc", "engagement_status": "Planned"}, A)],
        "work_order": [("WO-REG-001", "Configure reporting pack", {"assignee": "Casey Placeholder", "scheduled_for": d(5), "work_status": "In progress"}, A),
                       ("WO-REG-002", "Handover session", {"assignee": "Drew Fictional", "scheduled_for": d(12), "work_status": "Open"}, A)],
        "sla": [("SLA-001", "Standard support", {"response_target_minutes": 240, "resolution_target_minutes": 1200}, A),
                ("SLA-002", "Priority support", {"response_target_minutes": 60, "resolution_target_minutes": 480}, A)],
        "inventory_item": [("INV-001", "Laptop dock", {"sku": "DOCK-100", "quantity_on_hand": 8, "location": "Store room"}, A),
                           ("INV-002", "Monitor 27 inch", {"sku": "MON-270", "quantity_on_hand": 5, "location": "Store room"}, A)],
        "facility_request": [("FAC-001", "Meeting room booking", {"request_kind": "Facility", "needed_by": d(10)}, A),
                             ("FAC-002", "Travel to client site", {"request_kind": "Travel", "needed_by": d(25)}, R)],
        "account": [("ACC-001", "Northwind Example Ltd", {"segment": "Mid-market", "account_owner": "Emery Testperson"}, A),
                    ("ACC-002", "Contoso Sample Inc", {"segment": "Enterprise", "account_owner": "Avery Example"}, A)],
        "lead": [("LEAD-001", "Fabrikam enquiry", {"source": "Website", "stage": "Qualified"}, A),
                 ("LEAD-002", "Adventure Works enquiry", {"source": "Referral", "stage": "New"}, A)],
        "proposal": [("PROP-001", "Northwind phase 2 proposal", {"customer": "Northwind Example Ltd", "valid_until": d(30)}, A),
                     ("PROP-002", "Contoso support proposal", {"customer": "Contoso Sample Inc", "valid_until": d(45)}, R)],
        "order": [("ORD-001", "Annual support subscription", {"customer": "Northwind Example Ltd", "order_kind": "Subscription"}, A),
                  ("ORD-002", "Onboarding workshop", {"customer": "Fabrikam Placeholder LLC", "order_kind": "Order"}, A)],
        "feedback": [("FB-001", "Great onboarding", {"customer": "Northwind Example Ltd", "sentiment": "Positive"}, A),
                     ("FB-002", "Reports could be faster", {"customer": "Contoso Sample Inc", "sentiment": "Neutral"}, A)],
        "campaign": [("CMP-001", "Spring webinar", {"channel": "Email", "campaign_status": "Active"}, A),
                     ("CMP-002", "Case study series", {"channel": "Web", "campaign_status": "Planned"}, W)],
        "team_space": [("TS-001", "Platform Team space", {"purpose": "Engineering coordination", "space_owner": "Blake Sample"}, A),
                       ("TS-002", "Finance close room", {"purpose": "Month-end coordination", "space_owner": "Emery Testperson"}, A)],
        "meeting": [("MTG-001", "Weekly leadership sync", {"meeting_date": d(-7), "attendees": "Avery, Blake, Emery", "decisions": "Approve demo budget", "action_items": "Blake: draft roadmap"}, A),
                    ("MTG-002", "Quarterly planning", {"meeting_date": d(14), "attendees": "Leadership"}, W)],
        "form_request": [("FRM-001", "Laptop request", {"request_type": "Equipment", "requested_by": "Drew Fictional"}, A),
                         ("FRM-002", "Access request", {"request_type": "Access", "requested_by": "Casey Placeholder"}, R)],
        "vacancy": [("VAC-001", "Platform Engineer", {"department": "Engineering", "headcount": 2}, A),
                    ("VAC-002", "Accounts Assistant", {"department": "Finance", "headcount": 1}, R)],
        "goal": [("GOAL-001", "Reduce month-end close time", {"goal_owner": "Emery Testperson", "due_date": d(90)}, A),
                 ("GOAL-002", "Complete security training", {"goal_owner": "Gray Dummy", "due_date": d(60)}, A)],
        "budget": [("BUD-Y-001", "Operations budget (year)", {"fiscal_period": f"{year}", "currency": "USD", "planned_amount": "120000.00", "cost_centre": "OPS"}, A),
                   ("BUD-Q-001", "Engineering budget (quarter)", {"fiscal_period": f"{year}-Q{quarter}", "currency": "USD", "planned_amount": "400.00", "cost_centre": "ENG"}, A),
                   ("BUD-Q-002", "People budget (quarter)", {"fiscal_period": f"{year}-Q{quarter}", "currency": "USD", "planned_amount": "6000.00", "cost_centre": "PPL"}, A),
                   ("BUD-Q-003", "Finance budget (next quarter, draft)", {"fiscal_period": f"{year + 1}-Q1", "currency": "USD", "planned_amount": "9000.00", "cost_centre": "FIN"}, W)],
        "scenario": [("SCN-001", "Base case", {"horizon": "12 months", "assumptions": "Flat headcount; fictional figures", "uncertainty_note": "Demo scenario, not a forecast", "method": "Straight line"}, A),
                     ("SCN-002", "Growth case", {"horizon": "12 months", "assumptions": "Two extra hires; fictional", "uncertainty_note": "Demo scenario, not a forecast"}, R)],
        "automation": [("AUT-001", "Overdue invoice reminder", {"trigger": "Invoice overdue 7 days", "action": "Draft reminder", "scope": "AR invoices (read only)", "execution_mode": "Dry-run only", "stop_procedure": "Set to Disabled"}, A)],
        "shift_roster": [("ROST-001", "Platform Team week plan", {"employee_subject": "fx-emp-003", "shift_date": d(1), "start_time": "09:00", "end_time": "17:00", "arrangement": "Hybrid"}, A),
                         ("ROST-002", "Support cover", {"employee_subject": "fx-emp-004", "shift_date": d(2), "start_time": "10:00", "end_time": "18:00", "arrangement": "Remote"}, A)],
        "recovery_plan": [("REC-001", "Portal database restore", {"system": "Portal database", "rpo_minutes": 60, "rto_minutes": 240, "runbook_reference": "demo/runbooks/db-restore"}, A),
                          ("REC-002", "Identity provider recovery", {"system": "Identity provider", "runbook_reference": "demo/runbooks/idp"}, W)],
        "er_case": [("ER-001", "Workplace concern (sample)", {"case_type": "Grievance", "case_stage": "Opened", "next_milestone": "Acknowledge", "milestone_due": d(5)}, A)],
        "ai_use_case": [("AI-001", "Draft meeting summaries", {"purpose": "Summarise meeting notes", "approved_sources": "Meeting records only", "human_review_required": True,
                                                              "provenance_required": True, "deployment_mode": "Evaluation only", "risk_note": "No model connected; demo only"}, A)],
    }


def _seed_registers(db, org_id: str, today: date, now: datetime) -> int:
    from asaa_registers.catalog import TYPES, validate_data
    from asaa_registers.models import GovernedRecord
    created = 0
    for rtype, rows in _register_samples(today).items():
        assert rtype in TYPES, rtype
        for code, title, data, status in rows:
            existing = db.scalar(select(GovernedRecord.id).where(GovernedRecord.organization_id == org_id, GovernedRecord.register_type == rtype,
                                                                 GovernedRecord.code == code, GovernedRecord.revision == 1))
            _get_or_create(db, GovernedRecord, {"organization_id": org_id, "register_type": rtype, "code": code, "revision": 1},
                           {"owner_subject": _subject("FX-002"), "status": status, "data": validate_data(rtype, data), "created_by": SEED_ACTOR, "updated_by": SEED_ACTOR,
                            "effective_from": today - timedelta(days=30) if status == "Approved" else None, "review_due": today + timedelta(days=180),
                            "submitted_by": SEED_ACTOR if status in {"In Review", "Approved"} else None,
                            "reviewed_by": REVIEWER if status == "Approved" else None, "reviewed_at": now if status == "Approved" else None,
                            "review_reason": "Fictional demo approval" if status == "Approved" else None},
                           {"title": label(title, 240), "summary": marked()})
            created += existing is None
    return created


# ---------------------------------------------------------------------------------------------------------------------- the seed
def seed_demo(db, org_id: str, base: dict | None = None, owner_subject: str | None = None) -> dict:
    """Seed every demo workspace. `base` is the result of seed_fixtures (computed here when omitted). Returns per-workspace row counts."""
    from asaa_ap.models import (ARCreditNote, ARDebitNote, ARDispute, ARInvoice, ARReceipt, ARReceiptAllocation, AuditEvent, Supplier)
    from asaa_ap.procurement_models import PurchaseRequest, PurchaseRequestLine
    from asaa_attendance.models import AttendancePolicy, AttendanceCorrection, AttendanceRecord, Holiday, RosterAssignment, Shift
    from asaa_delivery.models import Engagement, ServiceDefinition
    from asaa_governance.models import MasterDataDomain, MasterDataRecordReference
    from asaa_identity.models import IdentitySubjectLink
    from asaa_notifications.models import NotificationMessage, NotificationPreference, NotificationTemplate
    from asaa_payables.models import (GoodsReceipt, GoodsReceiptLine, PaymentBatch, PaymentBatchItem, PurchaseOrder, PurchaseOrderLine, SupplierInvoice)
    from asaa_people.leave_policy import LeavePolicy
    from asaa_people.models import (CompensationRecord, Employee, EmployeeAsset, EmployeeExitCase, LeaveRequest, OnboardingAssignment, OnboardingTask,
                                    OnboardingTaskTemplate, OnboardingTemplate)
    from asaa_workforce_finance.models import ExpenseClaim, ExpensePolicyRule, TimeEntry, Timesheet

    base = base or seed_fixtures(db, org_id)
    now = datetime.now(timezone.utc)
    today = date.today()
    emp = base["employees"]
    cust = base["customers"]
    people = [code for code, *_ in PEOPLE]

    # Link the fixture people to login subjects so subject-keyed records (timesheets, expenses) resolve to an employee and its unit.
    for code in people:
        if db.scalar(select(IdentitySubjectLink.id).where(IdentitySubjectLink.organization_id == org_id, IdentitySubjectLink.employee_id == emp[code])) is None \
                and db.scalar(select(IdentitySubjectLink.id).where(IdentitySubjectLink.organization_id == org_id, IdentitySubjectLink.subject == _subject(code))) is None:
            db.add(IdentitySubjectLink(organization_id=org_id, employee_id=emp[code], subject=_subject(code), created_by=SEED_ACTOR))
    db.flush()
    subjects = {code: _subject(code) for code in people}
    if owner_subject and "owner" in emp:  # the owner's own "my timesheets / my expenses" views are populated too
        link = db.scalar(select(IdentitySubjectLink).where(IdentitySubjectLink.organization_id == org_id, IdentitySubjectLink.employee_id == emp["owner"]))
        subjects["owner"] = link.subject if link else owner_subject
    reviewer_subject = _subject("FX-005")

    # ---- Timesheets (some Submitted) -------------------------------------------------------------------------------------------
    monday = today - timedelta(days=today.weekday())
    ts_plan = [("FX-003", -1, "Submitted"), ("FX-004", -1, "Submitted"), ("FX-009", -1, "Approved"), ("FX-006", -1, "Draft"),
               ("FX-003", -2, "Approved"), ("FX-004", -2, "Approved"), ("FX-010", -1, "Submitted")]
    if "owner" in subjects:
        ts_plan += [("owner", -1, "Submitted"), ("owner", -2, "Approved")]
    for code, weeks, status in ts_plan:
        start = monday + timedelta(weeks=weeks)
        existing = db.scalar(select(Timesheet).where(Timesheet.organization_id == org_id, Timesheet.employee_subject == subjects[code], Timesheet.period_start == start))
        if existing is None:
            ts = Timesheet(organization_id=org_id, employee_subject=subjects[code], employee_reference=label(code, 128), period_start=start,
                           period_end=start + timedelta(days=6), status=status, total_hours=D("0"), created_by=subjects[code])
            if status == "Approved":
                ts.reviewed_by, ts.reviewed_at, ts.review_reason = reviewer_subject, now, "Fictional demo approval"
            db.add(ts)
            db.flush()
            total = D("0")
            for offset in range(5):
                hours = D("8.00") if offset < 4 else D("6.50")
                db.add(TimeEntry(organization_id=org_id, timesheet_id=ts.id, work_date=start + timedelta(days=offset), project_reference="FX-PROJECT-1",
                                 task_reference=f"FX-TASK-{offset + 1}", description=label(f"Demo work item {offset + 1}", 1000), hours=hours, billable=offset % 2 == 0))
                total += hours
            ts.total_hours = total
    db.flush()

    # ---- Expense policy and expenses (some Submitted) -------------------------------------------------------------------------
    for category, max_amount, receipt_above, status in (("travel", "500.00", "50.00", "Approved"), ("meals", "80.00", "25.00", "Approved"), ("software", "300.00", "0.00", "Pending Approval")):
        _get_or_create(db, ExpensePolicyRule, {"organization_id": org_id, "category_code": category},
                       {"currency": "USD", "max_amount": D(max_amount), "receipt_required_above": D(receipt_above), "on_violation": "flag", "status": status,
                        "updated_by": SEED_ACTOR, "approved_by": REVIEWER if status == "Approved" else None, "approved_at": now if status == "Approved" else None})
    exp_plan = [  # code, days ago, category, merchant, amount, status
        ("FX-003", 3, "travel", "Example Rail Co", "120.00", "Submitted"), ("FX-004", 5, "meals", "Sample Cafe", "42.50", "Submitted"),
        ("FX-009", 9, "software", "Placeholder Software", "99.00", "Submitted"), ("FX-006", 12, "travel", "Mock Airlines", "310.00", "Approved"),
        ("FX-003", 20, "meals", "Sample Cafe", "28.00", "Approved"), ("FX-010", 15, "travel", "Example Rail Co", "64.00", "Reimbursement Recorded"),
        ("FX-004", 2, "meals", "Sample Cafe", "15.00", "Draft"), ("FX-008", 7, "software", "Placeholder Software", "129.00", "Rejected"),
    ]
    if "owner" in subjects:
        exp_plan += [("owner", 4, "travel", "Example Rail Co", "75.00", "Submitted"), ("owner", 18, "meals", "Sample Cafe", "36.00", "Approved")]
    for code, ago, category, merchant, amount, status in exp_plan:
        description = label(f"{category.title()} expense at {merchant}", 1000)
        row = _get_or_create(db, ExpenseClaim, {"organization_id": org_id, "employee_subject": subjects[code], "expense_date": today - timedelta(days=ago),
                                                "category_code": category, "description": description},
                             {"merchant": merchant, "amount": D(amount), "currency": "USD", "receipt_reference": f"demo/receipts/{category}-{ago}",
                              "project_reference": "FX-PROJECT-1", "status": status, "created_by": subjects[code]})
        if status in {"Approved", "Rejected", "Reimbursement Recorded"} and row.reviewed_by is None:
            row.reviewed_by, row.reviewed_at, row.review_reason = reviewer_subject, now, "Fictional demo decision"
        if status == "Reimbursement Recorded" and row.reimbursed_at is None:
            row.reimbursed_at, row.reimbursed_by, row.reimbursement_reference = now, reviewer_subject, "FX-REIMB-001"
    db.flush()

    # ---- Procurement / purchase requests ---------------------------------------------------------------------------------------
    pr_plan = [("Team laptops (fictional)", "FX-003", "Submitted", [("Laptop 14 inch", "2", "each", "1200.00")]),
               ("Office chairs (fictional)", "FX-006", "Approved", [("Ergonomic chair", "4", "each", "250.00"), ("Delivery", "1", "lot", "60.00")]),
               ("Training licences (fictional)", "FX-009", "Draft", [("Course licence", "5", "seat", "80.00")]),
               ("Printer toner (fictional)", "FX-010", "Rejected", [("Toner cartridge", "3", "each", "75.00")])]
    pr_ids = {}
    for title, code, status, lines in pr_plan:
        total = sum(D(q) * D(p) for _, q, _, p in lines)
        pr = db.scalar(select(PurchaseRequest).where(PurchaseRequest.organization_id == org_id, PurchaseRequest.title == label(title, 200)))
        if pr is None:
            pr = PurchaseRequest(organization_id=org_id, title=label(title, 200), purpose=marked("Demo purchase request."), needed_by=today + timedelta(days=30), currency="USD",
                                 cost_center="ENG", project_reference="FX-PROJECT-1", estimated_total=total, status=status, requested_by=subjects[code], created_by=subjects[code],
                                 submitted_at=now if status != "Draft" else None)
            if status in {"Approved", "Rejected"}:
                pr.reviewed_by, pr.reviewed_at, pr.review_reason = reviewer_subject, now, "Fictional demo decision"
            for desc, qty, uom, price in lines:
                pr.lines.append(PurchaseRequestLine(description=desc, quantity=D(qty), unit_of_measure=uom, estimated_unit_cost=D(price), estimated_line_total=D(qty) * D(price)))
            db.add(pr)
            db.flush()
        pr_ids[title] = pr.id

    # ---- AP payables: supplier invoices, purchase orders, goods receipt, payment batch --------------------------------------------
    sup = {s.supplier_code: s for s in db.scalars(select(Supplier).where(Supplier.organization_id == org_id, Supplier.supplier_code.in_(["FXS-001", "FXS-002"])))}
    po1 = _get_or_create(db, PurchaseOrder, {"organization_id": org_id, "po_number": "FX-PO-001"},
                         {"supplier_id": sup["FXS-001"].id, "purchase_request_id": pr_ids["Office chairs (fictional)"],
                          "currency": "USD", "total": D("1060.00"), "status": "Issued", "created_by": SEED_ACTOR, "reviewed_by": REVIEWER, "reviewed_at": now,
                          "review_reason": "Fictional demo approval", "issued_at": now}, {"notes": marked()})
    if not po1.lines:
        po1.lines.append(PurchaseOrderLine(description="Ergonomic chair", quantity=D("4"), unit_of_measure="each", unit_price=D("250.00"), line_total=D("1000.00"), received_quantity=D("4")))
        po1.lines.append(PurchaseOrderLine(description="Delivery", quantity=D("1"), unit_of_measure="lot", unit_price=D("60.00"), line_total=D("60.00"), received_quantity=D("1")))
        db.flush()
    _get_or_create(db, PurchaseOrder, {"organization_id": org_id, "po_number": "FX-PO-002"},
                   {"supplier_id": sup["FXS-002"].id, "currency": "USD", "total": D("900.00"), "status": "Draft", "created_by": SEED_ACTOR}, {"notes": marked()})
    receipt = db.scalar(select(GoodsReceipt).where(GoodsReceipt.organization_id == org_id, GoodsReceipt.purchase_order_id == po1.id))
    if receipt is None:
        receipt = GoodsReceipt(organization_id=org_id, purchase_order_id=po1.id, received_date=today - timedelta(days=10), reference="FX-GRN-001", notes=marked(), received_by=SEED_ACTOR)
        for line in po1.lines:
            receipt.lines.append(GoodsReceiptLine(po_line_id=line.id, quantity=line.received_quantity))
        db.add(receipt)
    inv_plan = [("FX-SINV-001", "FXS-001", po1.id, "1060.00", "Paid", -25, 5), ("FX-SINV-002", "FXS-002", None, "450.00", "Approved", -8, 22),
                ("FX-SINV-003", "FXS-001", None, "275.00", "Captured", -2, 28), ("FX-SINV-004", "FXS-002", None, "1800.00", "Exception", -12, 18),
                ("FX-SINV-005", "FXS-001", None, "620.00", "Matched", -5, 25)]
    invoices = {}
    for number, scode, po_id, total, status, issued, _due in inv_plan:
        inv = _get_or_create(db, SupplierInvoice, {"organization_id": org_id, "supplier_id": sup[scode].id, "invoice_number": number},
                             {"purchase_order_id": po_id, "currency": "USD", "invoice_date": today + timedelta(days=issued), "due_date": today + timedelta(days=issued + 30),
                              "tax_total": D("0.00"), "total": D(total), "status": status, "captured_by": SEED_ACTOR,
                              "match_result": {"data_class": "TEMPORARY_TEST_DATA", "result": "exception" if status == "Exception" else "matched"} if status != "Captured" else None,
                              "reviewed_by": REVIEWER if status in {"Approved", "Paid", "Exception"} else None, "reviewed_at": now if status in {"Approved", "Paid", "Exception"} else None,
                              "review_reason": "Fictional demo decision" if status in {"Approved", "Paid", "Exception"} else None, "paid_at": now if status == "Paid" else None})
        invoices[number] = inv
    batch = db.scalar(select(PaymentBatch).where(PaymentBatch.organization_id == org_id, PaymentBatch.payment_reference == "FX-PAY-001"))
    if batch is None:
        batch = PaymentBatch(organization_id=org_id, currency="USD", total=D("1060.00"), status="Paid", created_by=SEED_ACTOR, approved_by=REVIEWER, approved_at=now,
                             paid_by=REVIEWER, paid_at=now, payment_reference="FX-PAY-001")
        batch.items.append(PaymentBatchItem(invoice_id=invoices["FX-SINV-001"].id, amount=D("1060.00")))
        db.add(batch)
    db.flush()

    # ---- AR: receipts (allocated), credit / debit notes, disputes --------------------------------------------------------------
    inv1, inv2, inv3 = (db.scalar(select(ARInvoice).where(ARInvoice.organization_id == org_id, ARInvoice.customer_id == cust[c])) for c in ("FXC-001", "FXC-002", "FXC-003"))
    rc1 = _get_or_create(db, ARReceipt, {"organization_id": org_id, "customer_id": cust["FXC-001"], "reference": "FX-RCPT-001"},
                         {"currency": "USD", "amount": D("200.00"), "received_date": today - timedelta(days=3), "method": "Bank transfer", "status": "Recorded", "created_by": SEED_ACTOR})
    if db.scalar(select(ARReceiptAllocation.id).where(ARReceiptAllocation.receipt_id == rc1.id)) is None:
        db.add(ARReceiptAllocation(receipt_id=rc1.id, invoice_id=inv1.id, amount=D("200.00")))
        inv1.status = "Partially Paid"
    rc2 = _get_or_create(db, ARReceipt, {"organization_id": org_id, "customer_id": cust["FXC-002"], "reference": "FX-RCPT-002"},
                         {"currency": "USD", "amount": D("450.00"), "received_date": today - timedelta(days=1), "method": "Card", "status": "Recorded", "created_by": SEED_ACTOR})
    if db.scalar(select(ARReceiptAllocation.id).where(ARReceiptAllocation.receipt_id == rc2.id)) is None:
        db.add(ARReceiptAllocation(receipt_id=rc2.id, invoice_id=inv2.id, amount=D("450.00")))
        inv2.status = "Partially Paid"
    _get_or_create(db, ARReceipt, {"organization_id": org_id, "customer_id": cust["FXC-003"], "reference": "FX-RCPT-003"},
                   {"currency": "USD", "amount": D("150.00"), "received_date": today, "method": "Bank transfer", "status": "Recorded", "created_by": SEED_ACTOR})  # unallocated
    credit = _get_or_create(db, ARCreditNote, {"organization_id": org_id, "invoice_id": inv2.id, "reason": label("Fictional pricing correction", 500)},
                            {"customer_id": cust["FXC-002"], "currency": "USD", "amount": D("50.00"), "status": "Approved", "created_by": SEED_ACTOR,
                             "reviewed_by": REVIEWER, "reviewed_at": now, "review_reason": "Fictional demo approval"})
    _get_or_create(db, ARCreditNote, {"organization_id": org_id, "invoice_id": inv3.id, "reason": label("Fictional goodwill credit", 500)},
                   {"customer_id": cust["FXC-003"], "currency": "USD", "amount": D("25.00"), "status": "Pending Approval", "created_by": SEED_ACTOR})
    _get_or_create(db, ARDebitNote, {"organization_id": org_id, "invoice_id": inv3.id, "reason": label("Fictional extra hours", 500)},
                   {"customer_id": cust["FXC-003"], "currency": "USD", "amount": D("75.00"), "status": "Pending Approval", "created_by": SEED_ACTOR})
    _get_or_create(db, ARDebitNote, {"organization_id": org_id, "invoice_id": inv1.id, "reason": label("Fictional late fee", 500)},
                   {"customer_id": cust["FXC-001"], "currency": "USD", "amount": D("10.00"), "status": "Rejected", "created_by": SEED_ACTOR,
                    "reviewed_by": REVIEWER, "reviewed_at": now, "review_reason": "Fictional demo decision"})
    _get_or_create(db, ARDispute, {"organization_id": org_id, "invoice_id": inv3.id, "reason": label("Fictional quantity query", 500)},
                   {"customer_id": cust["FXC-003"], "currency": "USD", "disputed_amount": D("100.00"), "status": "Open", "created_by": SEED_ACTOR})
    _get_or_create(db, ARDispute, {"organization_id": org_id, "invoice_id": inv2.id, "reason": label("Fictional price dispute", 500)},
                   {"customer_id": cust["FXC-002"], "currency": "USD", "disputed_amount": D("50.00"), "status": "Upheld", "created_by": SEED_ACTOR, "resolved_by": REVIEWER,
                    "resolved_at": now, "resolution_note": marked("Credited."), "credit_note_id": credit.id})
    db.flush()

    # ---- Leave policy and leave requests -----------------------------------------------------------------------------------------
    for category, days, status in (("Annual", "20.00", "Approved"), ("Sick", "10.00", "Approved"), ("Parental", "30.00", "Pending Approval")):
        _get_or_create(db, LeavePolicy, {"organization_id": org_id, "leave_category": category},
                       {"annual_entitlement_days": D(days), "carry_over_days": D("5.00") if category == "Annual" else D("0"), "enforce_balance": False, "status": status,
                        "updated_by": SEED_ACTOR, "approved_by": REVIEWER if status == "Approved" else None, "approved_at": now if status == "Approved" else None})
    leave_plan = [("FX-003", "Annual", 14, 18, "Submitted"), ("FX-004", "Sick", -4, -3, "Approved"), ("FX-009", "Annual", 30, 34, "Approved"),
                  ("FX-006", "Annual", 7, 8, "Rejected"), ("FX-010", "Sick", 2, 2, "Submitted"), ("FX-008", "Annual", 45, 52, "Submitted")]
    for code, category, start, end, status in leave_plan:
        reviewed = status in {"Approved", "Rejected"}
        _get_or_create(db, LeaveRequest, {"organization_id": org_id, "employee_id": emp[code], "leave_category": category, "start_date": today + timedelta(days=start),
                                          "end_date": today + timedelta(days=end)},
                       {"status": status, "created_by": subjects[code], "reviewer_subject": reviewer_subject if reviewed else None, "reviewed_at": now if reviewed else None,
                        "review_note": "Fictional demo decision" if reviewed else None}, {"reason": marked("Demo leave request.")})

    # ---- Attendance & shifts -------------------------------------------------------------------------------------------------------
    shifts = {}
    for code, name, start, end, brk, arrangement in (("DAY", "Day shift", time(9), time(17), 60, "On-site"), ("EARLY", "Early shift", time(7), time(15), 30, "On-site"),
                                                      ("REMOTE", "Remote day", time(9), time(17), 60, "Remote")):
        shifts[code] = _get_or_create(db, Shift, {"organization_id": org_id, "code": f"FX-{code}"},
                                      {"start_time": start, "end_time": end, "break_minutes": brk, "work_arrangement": arrangement, "status": "Active", "created_by": SEED_ACTOR},
                                      {"name": label(name, 120)})
    for offset in range(5):
        work_date = monday + timedelta(days=offset)
        for code, shift in (("FX-003", "DAY"), ("FX-004", "EARLY"), ("FX-009", "REMOTE"), ("FX-006", "DAY")):
            _get_or_create(db, RosterAssignment, {"organization_id": org_id, "employee_id": emp[code], "work_date": work_date},
                           {"shift_id": shifts[shift].id, "created_by": SEED_ACTOR})
    for offset, name in ((20, "Demo Founders Day"), (60, "Demo Midyear Break"), (90, "Demo Optional Festival")):
        _get_or_create(db, Holiday, {"organization_id": org_id, "holiday_date": today + timedelta(days=offset), "name": label(name, 160)},
                       {"optional": "Optional" in name, "created_by": SEED_ACTOR})
    _get_or_create(db, AttendancePolicy, {"organization_id": org_id},
                   {"overtime_threshold_minutes": 480, "status": "Approved", "updated_by": SEED_ACTOR, "approved_by": REVIEWER, "approved_at": now})
    first_record = None
    for back in range(1, 4):
        work_date = today - timedelta(days=back)
        if work_date.weekday() >= 5:
            continue
        for code, minutes in (("FX-003", 480), ("FX-004", 540 if back == 1 else 480), ("FX-009", 495)):
            clock_in = datetime.combine(work_date, time(9), tzinfo=timezone.utc)
            over = max(0, minutes - 480)
            rec = _get_or_create(db, AttendanceRecord, {"organization_id": org_id, "employee_id": emp[code], "work_date": work_date},
                                 {"clock_in": clock_in, "clock_out": clock_in + timedelta(minutes=minutes), "source": "self", "worked_minutes": minutes,
                                  "overtime_minutes": over, "overtime_status": "Pending" if over else "None"})
            first_record = first_record or rec
    if first_record is not None:
        corr_date = first_record.work_date
        _get_or_create(db, AttendanceCorrection, {"organization_id": org_id, "employee_id": first_record.employee_id, "work_date": corr_date, "record_id": first_record.id},
                       {"requested_clock_in": datetime.combine(corr_date, time(8, 45), tzinfo=timezone.utc), "requested_clock_out": datetime.combine(corr_date, time(17), tzinfo=timezone.utc),
                        "status": "Pending", "requested_by": subjects["FX-003"]}, {"reason": label("Forgot to clock in (demo)", 1000)})

    # ---- Employee assets ---------------------------------------------------------------------------------------------------------
    for code, ref, kind, status in (("FX-003", "FX-AST-001", "Laptop", "Issued"), ("FX-004", "FX-AST-002", "Laptop", "Issued"), ("FX-005", "FX-AST-003", "Monitor", "Issued"),
                                    ("FX-009", "FX-AST-004", "Access card", "Issued"), ("FX-008", "FX-AST-005", "Laptop", "Returned")):
        _get_or_create(db, EmployeeAsset, {"organization_id": org_id, "employee_id": emp[code], "asset_reference": ref},
                       {"asset_type": kind, "issued_on": today - timedelta(days=200), "returned_on": today - timedelta(days=5) if status == "Returned" else None,
                        "condition_on_issue": "Good", "condition_on_return": "Good" if status == "Returned" else None, "status": status, "created_by": SEED_ACTOR})

    # ---- Onboarding / offboarding ------------------------------------------------------------------------------------------------
    templates = {}
    for code, name, workflow, tasks in (
            ("FX-ONB", "Standard onboarding", "Onboarding", [("Create accounts", "IT"), ("Issue equipment", "IT"), ("Welcome meeting", "Manager")]),
            ("FX-OFF", "Standard offboarding", "Offboarding", [("Return equipment", "IT"), ("Handover notes", "Manager"), ("Revoke access", "IT")])):
        tpl = _get_or_create(db, OnboardingTemplate, {"organization_id": org_id, "template_code": code},
                             {"workflow_type": workflow, "employment_type": "Employee", "active": True, "created_by": SEED_ACTOR},
                             {"name": label(name, 180), "description": marked()})
        if db.scalar(select(OnboardingTaskTemplate.id).where(OnboardingTaskTemplate.template_id == tpl.id)) is None:
            for seq, (title, role) in enumerate(tasks, start=1):
                db.add(OnboardingTaskTemplate(template_id=tpl.id, title=title, owner_role=role, required=True, sequence=seq))
            db.flush()
        templates[workflow] = tpl
    for workflow, code, assign_status, done in (("Onboarding", "FX-009", "In Progress", 1), ("Onboarding", "FX-008", "Completed", 3), ("Offboarding", "FX-008", "In Progress", 1)):
        tpl = templates[workflow]
        a = _get_or_create(db, OnboardingAssignment, {"organization_id": org_id, "employee_id": emp[code], "template_id": tpl.id},
                           {"template_version": tpl.version, "status": assign_status, "target_date": today + timedelta(days=14), "created_by": SEED_ACTOR})
        if db.scalar(select(OnboardingTask.id).where(OnboardingTask.assignment_id == a.id)) is None:
            for index, tt in enumerate(db.scalars(select(OnboardingTaskTemplate).where(OnboardingTaskTemplate.template_id == tpl.id).order_by(OnboardingTaskTemplate.sequence))):
                finished = index < done
                db.add(OnboardingTask(organization_id=org_id, assignment_id=a.id, source_task_id=tt.id, title=tt.title, owner_role=tt.owner_role, required=True,
                                      status="Completed" if finished else "Pending", due_date=today + timedelta(days=7 + index), completed_at=now if finished else None,
                                      completed_by=REVIEWER if finished else None, evidence_reference=f"demo/evidence/{tt.id[:8]}" if finished else None))
        if workflow == "Offboarding":
            _get_or_create(db, EmployeeExitCase, {"organization_id": org_id, "employee_id": emp[code], "planned_last_day": today + timedelta(days=21)},
                           {"checklist_assignment_id": a.id, "reason_category": "Resignation", "status": "Open", "created_by": SEED_ACTOR}, {"notes": marked("Demo exit case.")})
    db.flush()

    # ---- Compensation, service catalogue, master data -----------------------------------------------------------------------------
    for index, code in enumerate(people):
        _get_or_create(db, CompensationRecord, {"organization_id": org_id, "employee_id": emp[code], "effective_from": today - timedelta(days=365)},
                       {"currency": "USD", "pay_basis": "Salary", "gross_amount": D(3000 + 250 * index), "frequency": "Monthly", "status": "Approved",
                        "created_by": SEED_ACTOR, "approved_by": REVIEWER, "approved_at": now, "approval_note": "Fictional demo approval"})
    services = {}
    for code, name, tier, status in (("FX-SVC-1", "Managed reporting", "Gold", "Active"), ("FX-SVC-2", "Implementation support", "Silver", "Active"),
                                     ("FX-SVC-3", "Advisory retainer", "Bronze", "Draft")):
        services[code] = _get_or_create(db, ServiceDefinition, {"organization_id": org_id, "code": code},
                                        {"owner_subject": subjects["FX-002"], "service_tier": tier, "status": status, "created_by": SEED_ACTOR,
                                         "reviewed_by": REVIEWER if status == "Active" else None, "review_reason": "Fictional demo approval" if status == "Active" else None},
                                        {"name": label(name, 160), "description": marked()})
    for engagement_code, service_code in (("FX-ENG-1", "FX-SVC-1"), ("FX-ENG-2", "FX-SVC-2")):
        engagement = db.get(Engagement, base["engagements"][engagement_code])
        if engagement.service_id is None:
            engagement.service_id = services[service_code].id
    for code, name, source in (("FX-MD-CUST", "Customers", "AR customer register"), ("FX-MD-SUPP", "Suppliers", "Supplier register"), ("FX-MD-PEOPLE", "People", "HR employee register")):
        domain = _get_or_create(db, MasterDataDomain, {"organization_id": org_id, "domain_code": code},
                                {"authoritative_source": source, "owner_subject": subjects["FX-005"], "steward_subject": subjects["FX-006"], "status": "Active",
                                 "created_by": SEED_ACTOR, "updated_by": SEED_ACTOR}, {"name": label(name, 160), "description": marked()})
        if code == "FX-MD-CUST":
            for ccode, cid in cust.items():
                _get_or_create(db, MasterDataRecordReference, {"organization_id": org_id, "domain_id": domain.id, "record_type": "ar_customer", "record_id": cid},
                               {"source_system": "ar", "source_record_id": ccode, "status": "Active", "created_by": SEED_ACTOR})
    db.flush()

    # ---- Governed registers (policies, risks, budgets, scenarios, projects, CRM, ...) --------------------------------------------
    _seed_registers(db, org_id, today, now)
    db.flush()

    # ---- Notifications --------------------------------------------------------------------------------------------------------------
    tmpl = {}
    for code, subject, body, variables in (("fx.leave.reviewed", "Your leave request was reviewed", "Decision: {decision}", ["decision"]),
                                           ("fx.expense.submitted", "An expense claim needs review", "Claim {claim} was submitted", ["claim"])):
        for channel in ("in_app", "email"):
            tmpl[(code, channel)] = _get_or_create(db, NotificationTemplate, {"organization_id": org_id, "code": code, "channel": channel},
                                                   {"allowed_variables": variables, "active": True, "created_by": SEED_ACTOR},
                                                   {"subject_template": label(subject, 300), "body_template": f"{DATA_BODY} {body}"})
    for code in ("FX-003", "FX-004", "FX-005"):
        _get_or_create(db, NotificationPreference, {"organization_id": org_id, "subject": subjects[code], "channel": "email"}, {"enabled": code != "FX-004"})
    for n, (code, tcode, status) in enumerate((("FX-003", "fx.leave.reviewed", "Sent"), ("FX-005", "fx.expense.submitted", "Pending"), ("FX-004", "fx.leave.reviewed", "Suppressed"),
                                                ("FX-005", "fx.expense.submitted", "Sent"))):
        _get_or_create(db, NotificationMessage, {"organization_id": org_id, "idempotency_key": f"fx-demo:{n}"},
                       {"recipient_subject": subjects[code], "template_code": tcode, "channel": "in_app", "body_text": f"{DATA_BODY} Demo notification {n + 1}", "status": status,
                        "attempts": 1 if status == "Sent" else 0, "next_attempt_at": now, "sent_at": now if status == "Sent" else None},
                       {"subject_text": label(f"Demo notification {n + 1}", 300)})

    # ---- Audit trail (a few clearly-marked demo events; real audit rows are written by the API) -------------------------------------
    for n, (action, entity, actor) in enumerate((("timesheet.submitted", "timesheet", subjects["FX-003"]), ("expense.submitted", "expense_claim", subjects["FX-004"]),
                                                  ("leave_request.reviewed", "leave_request", reviewer_subject), ("purchase_request.submitted", "purchase_request", subjects["FX-003"]))):
        entity_id = f"fx-demo-{n}"
        if db.scalar(select(AuditEvent.id).where(AuditEvent.organization_id == org_id, AuditEvent.entity_id == entity_id, AuditEvent.action == action)) is None:
            db.add(AuditEvent(organization_id=org_id, actor_id=actor, action=action, entity_type=entity, entity_id=entity_id, outcome="success",
                              details={"data_class": "TEMPORARY_TEST_DATA", "note": TEST_NOTE}, correlation_id=f"fx-demo-corr-{n}"))
    db.commit()
    return table_counts(db, org_id)


DATA_BODY = "TEMPORARY / TEST DATA."
TEST_NOTE = "Fictional demo event"


def table_counts(db, org_id: str) -> dict:
    """Row counts per portal workspace (organization scoped where the table has an organization column)."""
    from asaa_ap.models import ARCreditNote, ARDebitNote, ARDispute, ARReceipt, AuditEvent
    from asaa_ap.procurement_models import PurchaseRequest
    from asaa_attendance.models import AttendanceCorrection, AttendanceRecord, Holiday, RosterAssignment, Shift
    from asaa_delivery.models import ServiceDefinition
    from asaa_governance.models import MasterDataDomain
    from asaa_notifications.models import NotificationMessage, NotificationTemplate
    from asaa_payables.models import PaymentBatch, PurchaseOrder, SupplierInvoice
    from asaa_people.leave_policy import LeavePolicy
    from asaa_people.models import CompensationRecord, EmployeeAsset, EmployeeExitCase, LeaveRequest, OnboardingAssignment, OnboardingTemplate
    from asaa_registers.models import GovernedRecord
    from asaa_workforce_finance.models import ExpenseClaim, ExpensePolicyRule, Timesheet
    from sqlalchemy import func

    def registered(rtype: str) -> int:
        return db.scalar(select(func.count()).select_from(GovernedRecord).where(GovernedRecord.organization_id == org_id, GovernedRecord.register_type == rtype)) or 0

    models = {
        "timesheets": Timesheet, "expenses": ExpenseClaim, "expense_policy": ExpensePolicyRule, "purchase_requests": PurchaseRequest, "purchase_orders": PurchaseOrder,
        "supplier_invoices": SupplierInvoice, "payment_batches": PaymentBatch, "ar_receipts": ARReceipt, "ar_credit_notes": ARCreditNote, "ar_debit_notes": ARDebitNote,
        "ar_disputes": ARDispute, "leave_policy": LeavePolicy, "leave_requests": LeaveRequest, "shifts": Shift, "roster_assignments": RosterAssignment, "holidays": Holiday,
        "attendance_records": AttendanceRecord, "attendance_corrections": AttendanceCorrection, "employee_assets": EmployeeAsset, "onboarding_templates": OnboardingTemplate,
        "onboarding_assignments": OnboardingAssignment, "exit_cases": EmployeeExitCase, "compensation_records": CompensationRecord, "service_definitions": ServiceDefinition,
        "master_data_domains": MasterDataDomain, "notification_templates": NotificationTemplate, "notification_messages": NotificationMessage, "audit_events": AuditEvent,
    }
    counts = {name: _count(db, model, org_id) for name, model in models.items()}
    counts["budget_lines"] = registered("budget")
    counts["scenarios"] = registered("scenario")
    counts["governed_records"] = db.scalar(select(func.count()).select_from(GovernedRecord).where(GovernedRecord.organization_id == org_id)) or 0
    return counts


def main() -> int:
    from asaa_ap.config import get_settings
    refuse_unless_dev(get_settings())
    org_id = os.environ.get("DEMO_ORG_ID", "").strip() or DEFAULT_DEMO_ORG
    owner_email = os.environ.get("DEMO_USER_EMAIL", "").strip() or None
    owner_subject = os.environ.get("DEMO_USER_SUBJECT", "").strip() or None
    from asaa_ap.database import Base, SessionLocal, engine
    import asaa_ap.main  # noqa: F401  (registers every model on Base)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        base = seed_fixtures(db, org_id, owner_email, owner_subject)
        counts = seed_demo(db, org_id, base, owner_subject)
    print(f"Seeded fictional demo workspace for {org_id!r}: " + ", ".join(f"{k}={v}" for k, v in counts.items()) + ". Safe to re-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
