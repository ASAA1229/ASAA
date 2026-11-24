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
