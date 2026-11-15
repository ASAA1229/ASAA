"""Configurable leave policy: pending-owner-policy defaults, maker-checker approval, balances, optional enforcement."""
from datetime import date, timedelta

from asaa_ap.security import Principal, get_principal

PERMS = {"hr:employee:write", "hr:employee:read", "hr:leave:request", "hr:leave:review", "hr:leave:read", "hr:leave:policy:read", "hr:leave:policy:write", "hr:leave:policy:approve"}


def as_p(client, subject="hr-maker", perms=PERMS, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


def employee(client):
    return client.post("/api/v1/hr/employees", json={"first_name": "Leah", "last_name": "Vee", "employment_type": "Employee"}).json()


def request_leave(client, emp, start, days, category="Annual"):
    return client.post(f"/api/v1/hr/employees/{emp['id']}/leave-requests", json={
        "leave_category": category, "start_date": start.isoformat(), "end_date": (start + timedelta(days=days - 1)).isoformat(), "reason": "Time off"})


def approve_leave(client, request_id):
    as_p(client, "manager")
    r = client.post(f"/api/v1/hr/leave-requests/{request_id}/review", json={"decision": "Approved", "review_note": "ok"})
    as_p(client)
    return r


def test_policy_defaults_are_marked_pending_owner_policy_and_need_independent_approval(client):
    as_p(client)
    saved = client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "20", "carry_over_days": "5"}).json()
    assert saved["status"] == "Pending Approval" and saved["owner_approved"] is False and "PENDING OWNER POLICY" in saved["note"] and saved["enforce_balance"] is False
    assert client.post("/api/v1/hr/leave-policies/Annual/approve").status_code == 403  # maker cannot approve
    as_p(client, "owner-delegate")
    approved = client.post("/api/v1/hr/leave-policies/Annual/approve").json()
    assert approved["owner_approved"] is True and approved["note"] is None and approved["approved_by"] == "owner-delegate"
    assert client.post("/api/v1/hr/leave-policies/Annual/approve").status_code == 409
    as_p(client)
    changed = client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "22"}).json()
    assert changed["status"] == "Pending Approval" and changed["approved_by"] is None  # editing revokes approval
    assert client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "-1"}).status_code == 422
    assert client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "10", "unknown": 1}).status_code == 422


def test_balances_count_calendar_days_and_label_unapproved_policy(client):
    as_p(client)
    emp = employee(client)
    start = date(date.today().year, 3, 3)
    lr = request_leave(client, emp, start, 3).json()
    approve_leave(client, lr["id"])
    request_leave(client, emp, date(date.today().year, 6, 2), 2)  # submitted, not approved
    client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "20", "carry_over_days": "2"})
    body = client.get(f"/api/v1/hr/employees/{emp['id']}/leave-balance").json()
    annual = next(b for b in body["balances"] if b["leave_category"] == "Annual")
    assert (annual["entitlement_days"], annual["used_days"], annual["pending_days"], annual["remaining_days"]) == ("22.00", 3, 2, "17.00")
    assert annual["policy_status"] == "Pending Approval" and "PENDING OWNER POLICY" in annual["note"] and annual["enforced"] is False
    other = client.post(f"/api/v1/hr/employees/{emp['id']}/leave-requests", json={"leave_category": "Study", "start_date": date(date.today().year, 9, 1).isoformat(), "end_date": date(date.today().year, 9, 1).isoformat()})
    assert other.status_code == 201
    study = next(b for b in client.get(f"/api/v1/hr/employees/{emp['id']}/leave-balance").json()["balances"] if b["leave_category"] == "Study")
    assert study["entitlement_days"] is None and study["policy_status"] == "No policy configured"


def test_balance_is_only_enforced_for_an_approved_policy_with_enforce_balance(client):
    as_p(client)
    emp = employee(client)
    client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "3", "enforce_balance": True})
    assert request_leave(client, emp, date(2028, 2, 1), 10).status_code == 201  # policy not approved yet: informational only
    as_p(client, "owner-delegate")
    client.post("/api/v1/hr/leave-policies/Annual/approve")
    as_p(client)
    refused = request_leave(client, emp, date(2028, 5, 1), 1)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "leave_balance_exceeded"
    assert refused.json()["detail"]["requested_days"] == 1
    assert request_leave(client, emp, date(2029, 5, 1), 3).status_code == 201  # a different year has its own full entitlement
    assert request_leave(client, emp, date(2029, 8, 1), 1).status_code == 409


def test_leave_policy_permissions_and_organization_isolation(client):
    as_p(client)
    emp = employee(client)
    client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "20"})
    as_p(client, "reader", {"hr:leave:policy:read"})
    assert len(client.get("/api/v1/hr/leave-policies").json()) == 1
    assert client.put("/api/v1/hr/leave-policies/Annual", json={"annual_entitlement_days": "99"}).status_code == 403
    assert client.get(f"/api/v1/hr/employees/{emp['id']}/leave-balance").status_code == 403
    as_p(client, "other", PERMS, org="org-b")
    assert client.get("/api/v1/hr/leave-policies").json() == []
    assert client.get(f"/api/v1/hr/employees/{emp['id']}/leave-balance").status_code == 404
