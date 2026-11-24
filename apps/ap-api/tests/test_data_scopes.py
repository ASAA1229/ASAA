"""Data-scope enforcement (D3.14) and identity fixtures (D3.15): narrowing only, 404 outside scope, strict mode, per-module checks."""
import importlib.util
from pathlib import Path

import pytest

from asaa_ap.database import get_db
from asaa_ap.security import Principal, get_principal

SEED_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_identity_fixtures.py"
ORG = "org-a"


def load_seed():
    spec = importlib.util.spec_from_file_location("seed_identity_fixtures", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seeded(client):
    seed = load_seed()
    db = next(client.app.dependency_overrides[get_db]())
    data = seed.seed_fixtures(db, ORG)
    data["perms"] = frozenset(seed.FIXTURE_PERMISSIONS)
    data["seed"] = seed
    data["db"] = db
    return data


def act(client, data, subject, extra=()):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, ORG, data["perms"] | frozenset(extra))


def ids(response):
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()}


# ---- fixtures ------------------------------------------------------------------------------------------------------

def test_seed_is_idempotent_fictional_and_dev_only(client, seeded):
    seed = seeded["seed"]
    again = seed.seed_fixtures(seeded["db"], ORG)
    assert again["employees"] == seeded["employees"] and again["assignments"] == seeded["assignments"]
    assert len(seeded["employees"]) == 10 and set(seed.ROLE_SCOPES) == {"Organization", "Unit", "Department", "Project", "Customer", "Record"}
    from sqlalchemy import select
    from asaa_people.models import Employee
    emails = seeded["db"].scalars(select(Employee.work_email).where(Employee.organization_id == ORG)).all()
    assert emails and all(e.endswith("@example.invalid") for e in emails)

    class Settings:
        environment = "production"
    with pytest.raises(SystemExit):
        seed.refuse_unless_dev(Settings)
    Settings.environment = "test"
    seed.refuse_unless_dev(Settings)


def test_owner_email_links_by_hr_email_only(client, seeded):
    seed, db = seeded["seed"], seeded["db"]
    out = seed.seed_fixtures(db, ORG, owner_email="owner@example.invalid", owner_subject="sub-owner")
    from sqlalchemy import select
    from asaa_identity.models import IdentitySubjectLink
    link = db.scalar(select(IdentitySubjectLink).where(IdentitySubjectLink.subject == "sub-owner"))
    assert link and link.employee_id == out["employees"]["owner"]


# ---- HR employees ----------------------------------------------------------------------------------------------------

def test_hr_unit_scope_includes_descendants_and_hides_others(client, seeded):
    act(client, seeded, "fx-unit-lead")  # unit OPS -> Engineering -> Platform Team
    e = seeded["employees"]
    visible = ids(client.get("/api/v1/hr/employees"))
    assert visible == {e[c] for c in ("FX-002", "FX-003", "FX-004", "FX-009")}
    assert client.get(f"/api/v1/hr/employees/{e['FX-003']}").status_code == 200
    assert client.get(f"/api/v1/hr/employees/{e['FX-005']}").status_code == 404  # Finance: outside, not 403
    assert client.get(f"/api/v1/hr/employees/{e['FX-005']}/employment-records").status_code == 404


def test_hr_department_scope_is_exact_and_record_scope_is_one_record(client, seeded):
    act(client, seeded, "fx-department-officer")
    e = seeded["employees"]
    assert ids(client.get("/api/v1/hr/employees")) == {e["FX-005"], e["FX-006"], e["FX-010"]}
    act(client, seeded, "fx-record-reader")  # record scope is an invoice id: no employee matches
    assert ids(client.get("/api/v1/hr/employees")) == set()


def test_hr_narrowing_versus_token_and_no_assignment_compat(client, seeded):
    e = seeded["employees"]
    act(client, seeded, "fx-org-admin")
    assert len(ids(client.get("/api/v1/hr/employees"))) == 10
    act(client, seeded, "someone-without-assignments")  # today's behaviour kept: organization-wide via the token
    assert len(ids(client.get("/api/v1/hr/employees"))) == 10
    client.app.dependency_overrides[get_principal] = lambda: Principal("fx-org-admin", ORG, frozenset({"ar:customer:read"}))
    assert client.get("/api/v1/hr/employees").status_code == 403  # the token must still carry the permission
    assert client.get(f"/api/v1/hr/employees/{e['FX-001']}").status_code == 403


def test_hr_writes_check_scope(client, seeded):
    act(client, seeded, "fx-unit-lead")
    e, u = seeded["employees"], seeded["units"]
    body = {"employment_type": "Employee", "status": "Active", "effective_from": "2999-01-01", "department_id": u["ENG"]}
    assert client.post(f"/api/v1/hr/employees/{e['FX-005']}/employment-records", json=body).status_code == 404
    assert client.post(f"/api/v1/hr/employees/{e['FX-002']}/employment-records", json={**body, "department_id": u["FIN"]}).status_code == 403
    assert client.post(f"/api/v1/hr/employees/{e['FX-002']}/employment-records", json=body).status_code == 201
    created = client.post("/api/v1/hr/employees", json={"first_name": "New", "last_name": "Person", "employment_type": "Employee"})
    assert created.status_code == 403 and created.json()["detail"]["code"] == "authorization_out_of_scope"


# ---- AR ------------------------------------------------------------------------------------------------------------------

def test_ar_customer_scope_for_customers_invoices_receipts_statements(client, seeded):
    c, inv = seeded["customers"], seeded["invoices"]
    act(client, seeded, "fx-customer-manager")  # customer FXC-001
    assert ids(client.get("/api/v1/ar/customers")) == {c["FXC-001"]}
    assert ids(client.get("/api/v1/ar/invoices")) == {inv["FXC-001"]}
    assert client.get(f"/api/v1/ar/customers/{c['FXC-002']}").status_code == 404
    assert client.get(f"/api/v1/ar/invoices/{inv['FXC-002']}").status_code == 404
    assert client.get(f"/api/v1/ar/customers/{c['FXC-001']}/statement").status_code == 200
    assert client.get(f"/api/v1/ar/customers/{c['FXC-002']}/statement").status_code == 404
    assert ids(client.get("/api/v1/ar/receipts")) == set()
    version = client.get(f"/api/v1/ar/invoices/{inv['FXC-002']}").status_code
    assert version == 404
    receipt = {"customer_id": c["FXC-002"], "currency": "USD", "amount": "10.00", "received_date": "2026-01-01"}
    assert client.post("/api/v1/ar/receipts", json=receipt).status_code == 404
    assert client.post("/api/v1/ar/customers", json={"legal_name": "Brand New Example Co"}).status_code == 403


def test_ar_record_scope_sees_only_that_record(client, seeded):
    c, inv = seeded["customers"], seeded["invoices"]
    act(client, seeded, "fx-record-reader")  # record = invoice FXC-002
    assert ids(client.get("/api/v1/ar/invoices")) == {inv["FXC-002"]}
    assert client.get(f"/api/v1/ar/invoices/{inv['FXC-002']}").status_code == 200
    assert client.get(f"/api/v1/ar/invoices/{inv['FXC-001']}").status_code == 404
    assert ids(client.get("/api/v1/ar/customers")) == set()


def test_ar_org_scope_and_unassigned_see_everything(client, seeded):
    act(client, seeded, "fx-org-admin")
    assert len(ids(client.get("/api/v1/ar/customers"))) == 3
    act(client, seeded, "nobody")
    assert len(ids(client.get("/api/v1/ar/invoices"))) == 3


# ---- delivery ------------------------------------------------------------------------------------------------------------

def test_delivery_project_and_customer_scopes(client, seeded):
    g, c = seeded["engagements"], seeded["customers"]
    act(client, seeded, "fx-project-lead")  # project FX-PROJECT-1 -> engagement FX-ENG-1
    assert ids(client.get("/api/v1/delivery/engagements")) == {g["FX-ENG-1"]}
    assert client.get(f"/api/v1/delivery/engagements/{g['FX-ENG-2']}").status_code == 404
    detail = client.get(f"/api/v1/delivery/engagements/{g['FX-ENG-1']}").json()
    milestone = detail["milestones"][0]["id"]
    orders = client.get("/api/v1/delivery/work-orders").json()
    assert [o["engagement_id"] for o in orders] == [g["FX-ENG-1"]]
    other = seeded["db"].execute(__import__("sqlalchemy").text("select id from dlv_milestones where engagement_id=:e"), {"e": g["FX-ENG-2"]}).scalar()
    assert client.post(f"/api/v1/delivery/milestones/{milestone}/deliver", json={"evidence": "fictional evidence"}).status_code == 200
    assert client.post(f"/api/v1/delivery/milestones/{other}/deliver", json={"evidence": "fictional evidence"}).status_code == 404
    act(client, seeded, "fx-customer-manager")  # customer FXC-001 owns engagement 1 as well
    assert ids(client.get("/api/v1/delivery/engagements")) == {g["FX-ENG-1"]}
    assert client.post("/api/v1/delivery/work-orders", json={"title": "Out of scope order", "engagement_id": g["FX-ENG-2"]}).status_code == 404


# ---- payroll -------------------------------------------------------------------------------------------------------------

def test_payroll_entries_follow_the_employee_unit(client, seeded):
    run, e, pe = seeded["payroll_run"], seeded["employees"], seeded["payroll_entries"]
    act(client, seeded, "fx-department-officer")
    assert ids(client.get(f"/api/v1/payroll/runs/{run}/entries")) == {pe["FX-005"], pe["FX-006"], pe["FX-010"]}
    act(client, seeded, "fx-unit-lead")
    assert ids(client.get(f"/api/v1/payroll/runs/{run}/entries")) == {pe[c] for c in ("FX-002", "FX-003", "FX-004", "FX-009")}
    act(client, seeded, "fx-unit-lead", extra=())
    body = {"employee_id": e["FX-005"], "currency": "USD", "gross_amount": "10.00", "deduction_total": "0.00", "net_amount": "10.00"}
    assert client.post(f"/api/v1/payroll/runs/{run}/entries", json=body).status_code == 404


# ---- strict mode, effective access, privileged -------------------------------------------------------------------------------

def test_strict_mode_refuses_unassigned_and_needs_a_privileged_permission(client, seeded):
    act(client, seeded, "admin")
    assert client.put("/api/v1/authorization/scope-mode", json={"mode": "strict", "reason": "tightening"}).status_code == 403
    act(client, seeded, "admin", extra={"authorization:scope-mode:write", "authorization:role:read"})
    assert client.get("/api/v1/authorization/scope-mode").json()["mode"] == "narrow"
    assert client.put("/api/v1/authorization/scope-mode", json={"mode": "strict", "reason": "tightening"}).status_code == 200
    from sqlalchemy import select
    from asaa_ap.models import AuditEvent
    assert seeded["db"].scalar(select(AuditEvent.id).where(AuditEvent.action == "authorization_scope_mode.changed")) is not None
    act(client, seeded, "nobody")
    refused = client.get("/api/v1/hr/employees")
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "authorization_not_assigned"
    act(client, seeded, "fx-unit-lead")
    assert client.get("/api/v1/hr/employees").status_code == 200  # assigned: still narrowed
    act(client, seeded, "admin", extra={"authorization:scope-mode:write"})
    assert client.put("/api/v1/authorization/scope-mode", json={"mode": "token", "reason": "diagnosing"}).status_code == 200
    act(client, seeded, "fx-unit-lead")
    assert len(ids(client.get("/api/v1/hr/employees"))) == 10  # token mode: today's behaviour


def test_expired_revoked_or_unapproved_assignments_do_not_narrow(client, seeded):
    from datetime import datetime, timedelta, timezone
    from asaa_governance.authorization import AuthorizationAssignment
    db = seeded["db"]
    row = db.get(AuthorizationAssignment, seeded["assignments"]["fx-unit-lead"])
    row.effective_to = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    act(client, seeded, "fx-unit-lead")
    assert len(ids(client.get("/api/v1/hr/employees"))) == 10  # nothing in force: unchanged token behaviour (narrowing only)
    row.effective_to, row.status = None, "Revoked"
    db.commit()
    assert len(ids(client.get("/api/v1/hr/employees"))) == 10


def test_effective_access_view_and_scope_reference_checks(client, seeded):
    act(client, seeded, "admin", extra={"authorization:assignment:read"})
    view = client.get("/api/v1/authorization/effective-access", params={"subject": "fx-unit-lead"}).json()
    assert view["assignments"][0]["scope_type"] == "Unit" and view["permissions"]["hr:employee:read"]["unrestricted"] is False
    assert seeded["units"]["PLT"] in view["permissions"]["hr:employee:read"]["units"]  # descendant included
    assert view["permissions"]["payroll:read"]["sensitive"] is True
    perms = {"authorization:role:write", "authorization:assignment:create"}
    act(client, seeded, "maker", extra=perms)
    role = client.post("/api/v1/authorization/roles", json={"role_code": "customer.pick", "name": "Customer pick", "scope_type": "Customer", "permissions": ["ar:customer:read"]})
    assert role.status_code == 201
    unit_role = client.post("/api/v1/authorization/roles", json={"role_code": "unit.pick", "name": "Unit pick", "scope_type": "Unit", "permissions": ["hr:employee:read"]}).json()
    assert unit_role["scope_type"] == "Unit"
    # activate via an independent reviewer, then check the scope reference must exist in the organization
    act(client, seeded, "reviewer", extra={"authorization:role:approve"})
    for r in (role.json(), unit_role):
        assert client.post(f"/api/v1/authorization/roles/{r['id']}/review", json={"expected_version": 1, "decision": "Approve", "reason": "reviewed ok"}).status_code == 200
    act(client, seeded, "maker", extra=perms)
    window = {"subject": "s1", "effective_from": "2020-01-01T00:00:00+00:00", "reason": "fixture check"}
    assert client.post("/api/v1/authorization/assignments", json={**window, "role_template_id": role.json()["id"], "scope_reference": "customer:does-not-exist"}).status_code == 422
    assert client.post("/api/v1/authorization/assignments", json={**window, "role_template_id": unit_role["id"], "scope_reference": f"unit:{seeded['units']['FIN']}"}).status_code == 201


def test_sensitive_templates_still_need_independent_review_and_are_flagged(client, seeded):
    act(client, seeded, "maker", extra={"authorization:role:write", "authorization:role:approve"})
    made = client.post("/api/v1/authorization/roles", json={"role_code": "pay.all", "name": "Payroll everywhere", "scope_type": "Organization", "permissions": ["payroll:read", "audit:read"]}).json()
    assert made["status"] == "Proposed"  # not usable until reviewed
    assert client.post(f"/api/v1/authorization/roles/{made['id']}/review", json={"expected_version": 1, "decision": "Approve", "reason": "self approval"}).status_code == 403
    from sqlalchemy import select
    from asaa_ap.models import AuditEvent
    event = seeded["db"].scalar(select(AuditEvent).where(AuditEvent.action == "authorization_role.proposed"))
    assert event.details["sensitive_permissions"] == ["audit:read", "payroll:read"]


def test_demo_org_defaults_to_the_realm_org_claim():
    assert load_seed().DEFAULT_DEMO_ORG == "asaa"


# ---- E3:D3.19 TEMPORARY / TEST DATA labels and production guard ----------------------------------------------------

def test_seed_labels_everything_and_relabels_an_old_seed(client, seeded):
    from sqlalchemy import select
    from asaa_ap.models import ARCustomer, Supplier
    from asaa_delivery.models import Engagement, Milestone, WorkOrder
    from asaa_governance.administration import OrganizationProfile, OrganizationUnit
    from asaa_governance.authorization import AuthorizationRoleTemplate
    from asaa_people.models import Employee
    seed, db = seeded["seed"], seeded["db"]

    def check():
        names = [db.scalar(select(OrganizationProfile.display_name).where(OrganizationProfile.organization_id == ORG))]
        names += db.scalars(select(OrganizationUnit.name).where(OrganizationUnit.organization_id == ORG)).all()
        names += db.scalars(select(ARCustomer.legal_name).where(ARCustomer.organization_id == ORG)).all()
        names += db.scalars(select(Supplier.legal_name).where(Supplier.organization_id == ORG)).all()
        names += db.scalars(select(Employee.preferred_name).where(Employee.organization_id == ORG)).all()
        names += db.scalars(select(Engagement.title).where(Engagement.organization_id == ORG)).all()
        names += db.scalars(select(Milestone.title).where(Milestone.organization_id == ORG)).all()
        names += db.scalars(select(WorkOrder.title).where(WorkOrder.organization_id == ORG)).all()
        names += db.scalars(select(AuthorizationRoleTemplate.name).where(AuthorizationRoleTemplate.organization_id == ORG)).all()
        assert len(names) > 30 and all(n.startswith("TEMPORARY / TEST DATA – ") for n in names), [n for n in names if not (n or "").startswith("TEMPORARY")]
        for role in db.scalars(select(AuthorizationRoleTemplate).where(AuthorizationRoleTemplate.organization_id == ORG)):
            assert "TEMPORARY_TEST_DATA" in role.description and role.role_code.startswith("fixture.")
        assert all("TEMPORARY_TEST_DATA" in (s.notes or "") for s in db.scalars(select(Supplier)))
    check()
    # simulate an older unlabelled seed, then re-run: the labels come back without duplicating rows
    for unit in db.scalars(select(OrganizationUnit)):
        unit.name = unit.name.removeprefix(seed.TEST_PREFIX)
    for m in db.scalars(select(Milestone)):
        m.title = m.title.removeprefix(seed.TEST_PREFIX)
    db.commit()
    count = len(db.scalars(select(Milestone.id)).all())
    seed.seed_fixtures(db, ORG)
    check()
    assert len(db.scalars(select(Milestone.id)).all()) == count
    assert len(seed.label("x" * 500, 160)) == 160 and seed.label(seed.label("A")) == seed.label("A")


def test_fixture_roles_are_ignored_in_production(client, seeded, monkeypatch, caplog):
    from datetime import datetime, timezone
    from asaa_governance import scope
    db = seeded["db"]
    now = datetime.now(timezone.utc)
    assert scope.active_assignments(db, ORG, "fx-org-admin", now)
    monkeypatch.setattr(scope, "get_settings", lambda: type("S", (), {"environment": "production"})())
    with caplog.at_level("WARNING"):
        assert scope.active_assignments(db, ORG, "fx-org-admin", now) == []
        assert scope.active_assignments(db, ORG, "fx-unit-lead", now, "hr:employee:read") == []
    assert "fixture role assignment" in caplog.text and "fx-" not in caplog.text
    monkeypatch.setattr(scope, "get_settings", lambda: type("S", (), {"environment": "development"})())
    assert scope.active_assignments(db, ORG, "fx-org-admin", now)


# ---- E3:D3.21 data-scope gaps: AR adjustments, receipt allocation, reports, payroll run-level routes ----------------------------

AR_ADJ = {"ar:debit:write", "ar:debit:read", "ar:debit:approve", "ar:refund:write", "ar:refund:read", "ar:refund:approve", "ar:refund:record",
          "ar:dispute:write", "ar:dispute:read", "ar:dispute:resolve", "ar:receipt:allocate"}
PAY_RUN = {"payroll:run:submit", "payroll:run:approve", "payroll:run:close", "payroll:period:close", "payroll:accounting:read", "payroll:rules:write"}
REPORT_EXTRA = {"supplier:read", "expense:claim:read:all", "report:lineage:read", "report:analytics:read", "hr:leave:read", "ar:credit:read"}


def only_token(client, subject, permissions):
    """A principal whose token carries exactly these permissions (the assignments still list more)."""
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, ORG, frozenset(permissions))


def widen_fixture_roles(seeded, permissions):
    """The fixture roles only grant the base permissions; give them the ones under test (an assignment narrows only permissions its role grants)."""
    from sqlalchemy import select
    from asaa_governance.authorization import AuthorizationRoleTemplate
    db = seeded["db"]
    for role in db.scalars(select(AuthorizationRoleTemplate)):
        role.permissions = sorted(set(role.permissions) | set(permissions))
    db.commit()


def ar_world(client, seeded):
    """Debit note, dispute, receipt and refund for customers FXC-001 (in the customer-manager scope) and FXC-002 (outside it)."""
    widen_fixture_roles(seeded, AR_ADJ)
    c, inv = seeded["customers"], seeded["invoices"]
    act(client, seeded, "fx-org-admin", extra=AR_ADJ)
    world = {}
    for code in ("FXC-001", "FXC-002"):
        debit = client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv[code], "amount": "5.00", "reason": "fixture debit"})
        dispute = client.post("/api/v1/ar/disputes", json={"invoice_id": inv[code], "disputed_amount": "5.00", "reason": "fixture dispute"})
        receipt = client.post("/api/v1/ar/receipts", json={"customer_id": c[code], "currency": "USD", "amount": "50.00", "received_date": "2026-01-01"})
        assert debit.status_code == dispute.status_code == receipt.status_code == 201, (debit.text, dispute.text, receipt.text)
        refund = client.post("/api/v1/ar/refunds", json={"receipt_id": receipt.json()["id"], "amount": "10.00", "reason": "fixture refund"})
        assert refund.status_code == 201, refund.text
        world[code] = {"debit": debit.json()["id"], "dispute": dispute.json()["id"], "receipt": receipt.json()["id"], "refund": refund.json()["id"]}
    return world


def test_ar_adjustments_follow_the_customer_scope(client, seeded):
    world = ar_world(client, seeded)
    inv = seeded["invoices"]
    act(client, seeded, "fx-customer-manager", extra=AR_ADJ)  # customer FXC-001 only
    assert ids(client.get("/api/v1/ar/debit-notes")) == {world["FXC-001"]["debit"]}
    assert ids(client.get("/api/v1/ar/refunds")) == {world["FXC-001"]["refund"]}
    assert ids(client.get("/api/v1/ar/disputes")) == {world["FXC-001"]["dispute"]}
    # creating against another customer's invoice or receipt is 404, in scope still works
    other = world["FXC-002"]
    assert client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv["FXC-002"], "amount": "1.00", "reason": "out of scope"}).status_code == 404
    assert client.post("/api/v1/ar/disputes", json={"invoice_id": inv["FXC-002"], "disputed_amount": "1.00", "reason": "out of scope"}).status_code == 404
    assert client.post("/api/v1/ar/refunds", json={"receipt_id": other["receipt"], "amount": "1.00", "reason": "out of scope"}).status_code == 404
    assert client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv["FXC-001"], "amount": "1.00", "reason": "in scope"}).status_code == 201
    # acting on another customer's records is 404 (never 403, never a state change)
    review = {"decision": "approve", "reason": "looks fine"}
    assert client.post(f"/api/v1/ar/debit-notes/{other['debit']}/review", json=review).status_code == 404
    assert client.post(f"/api/v1/ar/refunds/{other['refund']}/review", json=review).status_code == 404
    assert client.post(f"/api/v1/ar/refunds/{other['refund']}/record-payment", json={"payment_reference": "ref-1"}).status_code == 404
    assert client.post(f"/api/v1/ar/disputes/{other['dispute']}/resolve", json={"outcome": "Rejected", "note": "no grounds"}).status_code == 404
    assert client.post(f"/api/v1/ar/disputes/{other['dispute']}/withdraw").status_code == 404
    assert client.post(f"/api/v1/ar/debit-notes/{world['FXC-001']['debit']}/review", json=review).status_code == 200
    assert client.post(f"/api/v1/ar/refunds/{world['FXC-001']['refund']}/review", json=review).status_code == 200
    act(client, seeded, "fx-org-admin", extra=AR_ADJ)  # the out-of-scope records were left untouched
    assert {r["id"]: r["status"] for r in client.get("/api/v1/ar/debit-notes").json()}[other["debit"]] == "Pending Approval"
    assert {r["id"]: r["status"] for r in client.get("/api/v1/ar/refunds").json()}[other["refund"]] == "Pending Approval"


def test_ar_adjustments_narrowing_versus_token(client, seeded):
    world = ar_world(client, seeded)
    both = {world[c]["debit"] for c in world}
    act(client, seeded, "fx-org-admin", extra=AR_ADJ)
    assert ids(client.get("/api/v1/ar/debit-notes")) >= both
    act(client, seeded, "someone-without-assignments", extra=AR_ADJ)  # no assignment: organization-wide through the token, as before
    assert ids(client.get("/api/v1/ar/debit-notes")) >= both
    # an assignment never widens the token: a token without the permission is refused whatever the role says
    only_token(client, "fx-org-admin", {"ar:invoice:read"})
    assert client.get("/api/v1/ar/debit-notes").status_code == 403 and client.get("/api/v1/ar/refunds").status_code == 403
    # a record scope narrows too: invoice FXC-002 is the only record, so no debit note (a different entity) is listed
    act(client, seeded, "fx-record-reader", extra=AR_ADJ)
    assert ids(client.get("/api/v1/ar/debit-notes")) == set()


def test_receipt_allocation_invoice_lookup_is_scoped(client, seeded):
    from datetime import datetime, timedelta, timezone
    from asaa_governance.authorization import AuthorizationAssignment
    world = ar_world(client, seeded)
    inv, db = seeded["invoices"], seeded["db"]
    template = db.get(AuthorizationAssignment, seeded["assignments"]["fx-record-reader"]).role_template_id
    db.add(AuthorizationAssignment(organization_id=ORG, role_template_id=template, subject="fx-receipt-record", scope_reference=f"record:{world['FXC-001']['receipt']}",
                                   effective_from=datetime.now(timezone.utc) - timedelta(days=1), reason="fixture", status="Approved", created_by="seed"))
    db.commit()
    act(client, seeded, "fx-receipt-record", extra=AR_ADJ)  # the receipt record is in scope, its invoice (another record) is not
    body = {"invoice_id": inv["FXC-001"], "amount": "10.00"}
    refused = client.post(f"/api/v1/ar/receipts/{world['FXC-001']['receipt']}/allocations", json=body)
    assert refused.status_code == 404 and refused.json()["detail"]["code"] == "invoice_not_found"
    act(client, seeded, "fx-customer-manager", extra=AR_ADJ)  # customer scope covers receipt and invoice
    assert client.post(f"/api/v1/ar/receipts/{world['FXC-001']['receipt']}/allocations", json=body).status_code == 200
    assert client.post(f"/api/v1/ar/receipts/{world['FXC-002']['receipt']}/allocations", json={"invoice_id": inv["FXC-002"], "amount": "10.00"}).status_code == 404


def test_reports_summary_is_narrowed_to_the_callers_scope(client, seeded):
    from sqlalchemy import select
    from asaa_people.models import PayrollRun
    widen_fixture_roles(seeded, AR_ADJ | PAY_RUN | REPORT_EXTRA)
    seeded["db"].scalar(select(PayrollRun)).status = "Closed"
    seeded["db"].commit()
    extra = REPORT_EXTRA | PAY_RUN
    act(client, seeded, "fx-org-admin", extra=extra)
    full = client.get("/api/v1/reports/summary").json()["sections"]
    assert full["receivables"]["data"]["invoices_by_status"] == {"Issued": 3} and full["customers"]["data"]["customers_by_status"] == {"Active": 3}
    assert full["workforce"]["data"]["employees_by_status"] == {"Active": 10}
    assert full["payroll_accounting"]["data"]["closed_run_totals_by_currency"]["USD"]["gross"] == "10000.00" and "suppliers" in full
    act(client, seeded, "fx-customer-manager", extra=extra)  # customer FXC-001
    narrow = client.get("/api/v1/reports/summary").json()["sections"]
    assert narrow["receivables"]["data"]["invoices_by_status"] == {"Issued": 1} and narrow["customers"]["data"]["customers_by_status"] == {"Active": 1}
    assert "suppliers" not in narrow and "expenses" not in narrow  # no customer or unit dimension: withheld from a restricted caller
    assert narrow["workforce"]["data"]["employees_by_status"] == {}  # customer scope has no employee dimension
    assert narrow["payroll_accounting"]["data"]["closed_run_totals_by_currency"] == {}
    act(client, seeded, "fx-unit-lead", extra=extra)  # unit OPS: FX-002, FX-003, FX-004, FX-009
    unit = client.get("/api/v1/reports/summary").json()["sections"]
    assert unit["workforce"]["data"]["employees_by_status"] == {"Active": 4}
    assert unit["payroll_accounting"]["data"]["closed_run_totals_by_currency"]["USD"] == {"runs": 1, "gross": "4000.00", "deductions": "400.00", "net": "3600.00"}
    assert unit["receivables"]["data"]["invoices_by_status"] == {} and "suppliers" not in unit
    act(client, seeded, "fx-record-reader", extra=extra)  # record = invoice FXC-002
    assert client.get("/api/v1/reports/summary").json()["sections"]["receivables"]["data"]["invoices_by_status"] == {"Issued": 1}


def test_reports_narrowing_versus_token_and_strict_mode(client, seeded):
    widen_fixture_roles(seeded, REPORT_EXTRA)
    act(client, seeded, "someone-without-assignments", extra=REPORT_EXTRA)  # unassigned: organization-wide through the token
    sections = client.get("/api/v1/reports/summary").json()["sections"]
    assert sections["receivables"]["data"]["invoices_by_status"] == {"Issued": 3} and "suppliers" in sections
    only_token(client, "fx-customer-manager", {"ar:invoice:read"})  # an assignment cannot add what the token lacks
    only = client.get("/api/v1/reports/summary").json()["sections"]
    assert set(only) == {"receivables"} and only["receivables"]["data"]["invoices_by_status"] == {"Issued": 1}
    act(client, seeded, "admin", extra={"authorization:scope-mode:write"})
    assert client.put("/api/v1/authorization/scope-mode", json={"mode": "strict", "reason": "tightening"}).status_code == 200
    act(client, seeded, "nobody", extra=REPORT_EXTRA)  # strict: no assignment, the sections are withheld instead of failing the report
    assert client.get("/api/v1/reports/summary").json()["sections"] == {}


def test_report_analytics_and_lineage_follow_the_scope(client, seeded):
    widen_fixture_roles(seeded, REPORT_EXTRA)
    act(client, seeded, "fx-org-admin", extra=REPORT_EXTRA)
    org_wide = {d["dataset"]: d["record_count"] for d in client.get("/api/v1/reports/freshness").json()["datasets"]}
    assert org_wide["ar_invoices"] == 3 and org_wide["hr_employees"] == 10 and "ap_suppliers" in org_wide
    full = client.get("/api/v1/reports/analytics/working-capital-position").json()["by_currency"]["USD"]["receivables_outstanding"]
    act(client, seeded, "fx-customer-manager", extra=REPORT_EXTRA)
    scoped = {d["dataset"]: d["record_count"] for d in client.get("/api/v1/reports/freshness").json()["datasets"]}
    assert scoped["ar_invoices"] == 1 and scoped["hr_employees"] == 0 and "ap_suppliers" not in scoped
    trend = client.get("/api/v1/reports/analytics/trends", params={"dataset": "ar_invoices"}).json()
    assert sum(row["records"] for row in trend["series"]) == 1
    assert client.get("/api/v1/reports/analytics/trends", params={"dataset": "ap_suppliers"}).status_code == 403  # cannot be narrowed to a customer
    mine = client.get("/api/v1/reports/analytics/working-capital-position").json()["by_currency"]["USD"]["receivables_outstanding"]
    assert 0 < float(mine) < float(full)
    lineage = client.get("/api/v1/reports/lineage").json()
    assert "ap_suppliers" not in {d["name"] for d in lineage["datasets"]} and "ar_invoices" in {d["name"] for d in lineage["datasets"]}


def test_payroll_run_level_routes_follow_the_employee_scope(client, seeded):
    widen_fixture_roles(seeded, PAY_RUN)
    run, pe, e = seeded["payroll_run"], seeded["payroll_entries"], seeded["employees"]
    act(client, seeded, "fx-org-admin", extra=PAY_RUN)
    assert [r["id"] for r in client.get("/api/v1/payroll/runs").json()] == [run]
    assert client.get(f"/api/v1/payroll/runs/{run}/summary").json()["entry_count"] == 10
    act(client, seeded, "fx-unit-lead", extra=PAY_RUN)  # four of the ten entries
    summary = client.get(f"/api/v1/payroll/runs/{run}/summary").json()
    assert summary["entry_count"] == 4 and summary["gross_total"] == "4000.00" and summary["net_total"] == "3600.00"
    assert [r["id"] for r in client.get("/api/v1/payroll/runs").json()] == [run]  # visible through its in-scope entries
    assert client.get(f"/api/v1/payroll/runs/{run}/entries/{pe['FX-005']}/lines").status_code == 404  # another unit's entry
    assert client.get(f"/api/v1/payroll/runs/{run}/entries/{pe['FX-002']}/lines").status_code == 200
    # a run-level action touches every entry, so a restricted caller may not run it; the run itself is not hidden from them
    for call in (client.post(f"/api/v1/payroll/runs/{run}/submit", json={"review_note": "ready"}), client.post(f"/api/v1/payroll/runs/{run}/calculate")):
        assert call.status_code == 403 and call.json()["detail"]["code"] == "authorization_out_of_scope"
    body = {"currency": "USD", "gross_amount": "5.00", "deduction_total": "0.00", "net_amount": "5.00"}
    assert client.patch(f"/api/v1/payroll/entries/{pe['FX-005']}", json=body).status_code == 404
    act(client, seeded, "fx-record-reader", extra=PAY_RUN)  # record scope: no entry matches, so the run is invisible
    assert client.get("/api/v1/payroll/runs").json() == []
    assert client.get(f"/api/v1/payroll/runs/{run}/summary").status_code == 404
    assert client.post(f"/api/v1/payroll/runs/{run}/close").status_code == 404
    act(client, seeded, "fx-unit-lead", extra=PAY_RUN)
    assert client.post("/api/v1/payroll/periods/anything/close").status_code == 403  # period close needs the whole organization


def test_payroll_run_level_narrowing_versus_token(client, seeded):
    widen_fixture_roles(seeded, PAY_RUN)
    run = seeded["payroll_run"]
    act(client, seeded, "someone-without-assignments", extra=PAY_RUN)  # no assignment: organization-wide through the token
    assert client.get(f"/api/v1/payroll/runs/{run}/summary").json()["entry_count"] == 10
    assert client.post(f"/api/v1/payroll/runs/{run}/submit", json={"review_note": "ready"}).status_code == 200
    only_token(client, "fx-org-admin", {"ar:invoice:read"})  # token without the permission is still refused
    assert client.get("/api/v1/payroll/runs").status_code == 403
