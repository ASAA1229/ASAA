"""Governed registers: validation, maker-checker, revisions, isolation, audit (shared platform / governance / legal workspaces)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from asaa_ap.database import get_db
from asaa_ap.main import app
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_registers.catalog import TYPES


def perms(*types, actions=("read", "write", "review")):
    return {f"register:{t}:{a}" for t in types for a in actions}


ALL = perms(*TYPES)


def as_p(client, subject="maker", p=ALL, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(p))


@pytest.fixture
def db(client):
    session = next(app.dependency_overrides[get_db]())
    yield session
    session.close()


def policy(client, code="POL-001", **extra):
    body = {"code": code, "title": "Acceptable use policy", "summary": "Rules for using systems.", "data": {"document_type": "Policy"}, **extra}
    r = client.post("/api/v1/registers/policy", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, record, reviewer="checker"):
    as_p(client)
    sub = client.post(f"/api/v1/registers/{record['register_type']}/{record['id']}/submit", json={"expected_version": record["version"]})
    assert sub.status_code == 200, sub.text
    as_p(client, reviewer)
    ok = client.post(f"/api/v1/registers/{record['register_type']}/{record['id']}/review",
                     json={"expected_version": sub.json()["version"], "decision": "Approve", "reason": "Reviewed and accepted"})
    assert ok.status_code == 200, ok.text
    as_p(client)
    return ok.json()


def test_catalogue_lists_only_readable_registers_with_field_specs(client):
    as_p(client, p=perms("policy", "risk", actions=("read",)))
    types = client.get("/api/v1/registers/types").json()
    assert {t["key"] for t in types} == {"policy", "risk"}
    assert next(t for t in types if t["key"] == "risk")["fields"][1]["choices"] == ["Low", "Medium", "High"]
    as_p(client, p=set())
    assert client.get("/api/v1/registers/types").json() == []


def test_create_list_filter_search_summary(client):
    as_p(client)
    policy(client, "POL-001")
    policy(client, "POL-002", review_due=(date.today() - timedelta(days=3)).isoformat())
    assert len(client.get("/api/v1/registers/policy").json()) == 2
    assert client.get("/api/v1/registers/policy?status=Approved").json() == []
    assert [r["code"] for r in client.get("/api/v1/registers/policy?q=pol-002").json()] == ["POL-002"]
    summary = client.get("/api/v1/registers/policy/summary").json()
    assert summary["by_status"]["Draft"] == 2 and summary["review_overdue"] == 0  # drafts are not counted as overdue reviews
    assert client.post("/api/v1/registers/policy", json={"code": "POL-001", "title": "Duplicate", "data": {"document_type": "Policy"}}).status_code == 409


def test_every_register_type_validates_its_own_fields(client):
    as_p(client)
    bad = {
        "policy": {"document_type": "Novel"}, "risk": {"likelihood": "High"}, "control": {"control_type": "Preventive", "frequency": "Hourly"},
        "obligation": {}, "contract": {"counterparty": "X", "contract_type": "Customer", "renewal_date": "tomorrow"},
        "retention_rule": {"data_category": "payroll", "retention_period_months": "ten", "disposal_method": "Delete"},
        "integration": {"kind": "Identity", "health_status": "Healthy", "credential_reference": "hunter2 with spaces!"},
        "security_incident": {"severity": "Catastrophic"},
    }
    for rtype, data in bad.items():
        r = client.post(f"/api/v1/registers/{rtype}", json={"code": "BAD-1", "title": "Invalid record", "data": data})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_register_data", (rtype, r.text)
    unknown = client.post("/api/v1/registers/policy", json={"code": "POL-9", "title": "Unknown field", "data": {"document_type": "Policy", "salary": "1"}})
    assert unknown.status_code == 422 and "unknown fields" in unknown.json()["detail"]["message"]
    good = {"contract": {"counterparty": "Globex", "contract_type": "Supplier", "renewal_date": "2027-03-31", "auto_renew": True},
            "retention_rule": {"data_category": "Employee records", "retention_period_months": 84, "disposal_method": "Archive"},
            "integration": {"kind": "Identity", "health_status": "Unknown", "credential_reference": "vault:asaa/scim-token"}}
    for rtype, data in good.items():
        assert client.post(f"/api/v1/registers/{rtype}", json={"code": "OK-1", "title": "Valid record", "data": data}).status_code == 201, rtype


def test_workflow_definition_graph_is_validated(client):
    as_p(client)
    ok = {"initial_state": "Draft", "states": ["Draft", "Review", "Done"],
          "transitions": [{"from": "Draft", "to": "Review", "action": "submit"}, {"from": "Review", "to": "Done", "action": "approve", "permission": "x:approve"},
                          {"from": "Review", "to": "Draft", "action": "return"}]}
    assert client.post("/api/v1/registers/workflow_definition", json={"code": "WF-1", "title": "Two step approval", "data": ok}).status_code == 201
    cases = {
        "bad initial": {**ok, "initial_state": "Nope"},
        "undeclared target": {**ok, "transitions": ok["transitions"] + [{"from": "Done", "to": "Ghost", "action": "x"}]},
        "unreachable": {**ok, "states": ok["states"] + ["Orphan"]},
        "duplicate action": {**ok, "transitions": ok["transitions"] + [{"from": "Draft", "to": "Done", "action": "submit"}]},
        "extra key": {**ok, "transitions": [{"from": "Draft", "to": "Review", "action": "submit", "script": "rm -rf"}] + ok["transitions"][1:]},
    }
    for name, data in cases.items():
        r = client.post("/api/v1/registers/workflow_definition", json={"code": "WF-" + name[:3].upper(), "title": "Invalid workflow", "data": data})
        assert r.status_code == 422, (name, r.text)


def test_lifecycle_submit_review_maker_checker_edit_lock_and_audit(client, db):
    as_p(client)
    rec = policy(client)
    upd = client.patch(f"/api/v1/registers/policy/{rec['id']}", json={"expected_version": rec["version"], "title": "Acceptable use policy v1"})
    assert upd.status_code == 200 and upd.json()["version"] == rec["version"] + 1
    assert client.patch(f"/api/v1/registers/policy/{rec['id']}", json={"expected_version": rec["version"], "title": "stale"}).status_code == 409
    sub = client.post(f"/api/v1/registers/policy/{rec['id']}/submit", json={"expected_version": upd.json()["version"]}).json()
    assert sub["status"] == "In Review"
    assert client.patch(f"/api/v1/registers/policy/{rec['id']}", json={"expected_version": sub["version"], "title": "xx"}).status_code == 409  # locked
    # maker cannot review own record, even with review permission
    own = client.post(f"/api/v1/registers/policy/{rec['id']}/review", json={"expected_version": sub["version"], "decision": "Approve", "reason": "self approval"})
    assert own.status_code == 403 and own.json()["detail"]["code"] == "maker_cannot_review_own_record"
    as_p(client, "checker")
    assert client.post(f"/api/v1/registers/policy/{rec['id']}/review", json={"expected_version": sub["version"], "decision": "Reject", "reason": "needs work"}).status_code == 200
    again = client.get(f"/api/v1/registers/policy/{rec['id']}").json()
    assert again["status"] == "Draft" and again["review_reason"] == "needs work"
    done = approve(client, again)
    assert done["status"] == "Approved" and done["effective_from"] == date.today().isoformat() and done["reviewed_by"] == "checker"
    actions = [e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.entity_id == rec["id"])).all()]
    assert {"register_record.created", "register_record.updated", "register_record.submitted", "register_record.reviewed"} <= set(actions)


def test_revisions_supersede_and_retire_requires_reason(client):
    as_p(client)
    v1 = approve(client, policy(client))
    assert client.post(f"/api/v1/registers/policy/{v1['id']}/review", json={"expected_version": v1["version"], "decision": "Approve", "reason": "again"}).status_code == 409
    rev = client.post(f"/api/v1/registers/policy/{v1['id']}/revise", json={"expected_version": v1["version"]})
    assert rev.status_code == 201 and rev.json()["revision"] == 2 and rev.json()["status"] == "Draft"
    assert client.post(f"/api/v1/registers/policy/{v1['id']}/revise", json={"expected_version": v1["version"]}).json()["detail"]["code"] == "open_revision_exists"
    v2 = approve(client, rev.json())
    assert v2["status"] == "Approved"
    rows = {r["revision"]: r for r in client.get("/api/v1/registers/policy").json()}
    assert rows[1]["status"] == "Retired" and "Superseded by revision 2" in rows[1]["review_reason"]
    assert client.post(f"/api/v1/registers/policy/{v2['id']}/retire", json={"expected_version": v2["version"]}).status_code == 422
    retired = client.post(f"/api/v1/registers/policy/{v2['id']}/retire", json={"expected_version": v2["version"], "reason": "Replaced by a new standard"})
    assert retired.status_code == 200 and retired.json()["status"] == "Retired"


def test_review_overdue_is_reported_for_approved_records(client):
    as_p(client)
    rec = policy(client, review_due=(date.today() - timedelta(days=1)).isoformat())
    approve(client, rec)
    assert client.get("/api/v1/registers/policy/summary").json()["review_overdue"] == 1


def test_permissions_are_per_register_and_per_action(client):
    as_p(client)
    rec = policy(client)
    as_p(client, "reader", perms("policy", actions=("read",)))
    assert client.get("/api/v1/registers/policy").status_code == 200
    assert client.post("/api/v1/registers/policy", json={"code": "POL-5", "title": "Not allowed", "data": {"document_type": "Policy"}}).status_code == 403
    assert client.get("/api/v1/registers/risk").status_code == 403  # a different register
    as_p(client, "writer", perms("policy", actions=("read", "write")))
    sub = client.post(f"/api/v1/registers/policy/{rec['id']}/submit", json={"expected_version": rec["version"]}).json()
    assert client.post(f"/api/v1/registers/policy/{rec['id']}/review", json={"expected_version": sub["version"], "decision": "Approve", "reason": "no perm"}).status_code == 403
    assert client.get("/api/v1/registers/not_a_type").status_code == 403
    as_p(client, "admin", {"register:not_a_type:read"})
    assert client.get("/api/v1/registers/not_a_type").status_code == 404


def test_organization_isolation(client):
    as_p(client)
    rec = policy(client)
    as_p(client, "other", ALL, org="org-b")
    assert client.get("/api/v1/registers/policy").json() == []
    assert client.get(f"/api/v1/registers/policy/{rec['id']}").status_code == 404
    assert client.patch(f"/api/v1/registers/policy/{rec['id']}", json={"expected_version": 1, "title": "hijack"}).status_code == 404
    assert client.post(f"/api/v1/registers/policy/{rec['id']}/submit", json={"expected_version": 1}).status_code == 404
    assert client.get("/api/v1/registers/policy/summary").json()["by_status"]["Draft"] == 0
    # same code is allowed in another organization
    assert client.post("/api/v1/registers/policy", json={"code": "POL-001", "title": "Org B policy", "data": {"document_type": "Policy"}}).status_code == 201
    # a record of one type cannot be read through another register's URL
    as_p(client)
    assert client.get(f"/api/v1/registers/risk/{rec['id']}").status_code == 404


def test_mass_assignment_and_date_validation(client):
    as_p(client)
    r = client.post("/api/v1/registers/policy", json={"code": "POL-7", "title": "Mass assignment", "status": "Approved", "organization_id": "org-b", "data": {"document_type": "Policy"}})
    assert r.status_code == 422
    bad = client.post("/api/v1/registers/policy", json={"code": "POL-8", "title": "Dates wrong", "effective_from": "2026-12-01", "effective_to": "2026-01-01",
                                                          "data": {"document_type": "Policy"}})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "effective_to_before_effective_from"


def sample_data(spec):
    data = {}
    for f in spec.fields:
        if not f.required:
            continue
        data[f.name] = {"enum": f.choices[0] if f.choices else "", "str": "sample", "int": 1, "bool": True, "date": "2026-12-01", "ref": "vault:sample/key",
                        "strlist": ["Start", "End"], "transitions": [{"from": "Start", "to": "End", "action": "finish"}]}[f.kind]
        if f.name == "initial_state":
            data[f.name] = "Start"
    return data


@pytest.mark.parametrize("rtype", sorted(TYPES))
def test_every_register_type_accepts_a_minimal_valid_record_and_runs_the_review_flow(client, rtype):
    as_p(client)
    created = client.post(f"/api/v1/registers/{rtype}", json={"code": "S-1", "title": "Sample record", "data": sample_data(TYPES[rtype])})
    assert created.status_code == 201, (rtype, created.text)
    assert approve(client, created.json())["status"] == "Approved"
    required = [f for f in TYPES[rtype].fields if f.required]
    if required:  # a record missing its required fields is refused
        assert client.post(f"/api/v1/registers/{rtype}", json={"code": "S-2", "title": "Missing fields", "data": {}}).status_code == 422
    assert TYPES[rtype].workspace
