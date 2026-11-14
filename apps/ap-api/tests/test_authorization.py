from datetime import datetime, timedelta, timezone

from asaa_ap.security import Principal, get_principal


PERMS = {
    "authorization:role:read", "authorization:role:write", "authorization:role:approve",
    "authorization:assignment:read", "authorization:assignment:create",
    "authorization:assignment:approve", "authorization:assignment:revoke",
}


def as_subject(client, subject="admin", permissions=None, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        subject, org, frozenset(PERMS if permissions is None else permissions)
    )


def create_active_role(client):
    created = client.post("/api/v1/authorization/roles", json={
        "role_code": "finance.reviewer", "name": "Finance reviewer",
        "scope_type": "Organization", "permissions": ["invoice:read", "invoice:approve"]
    })
    assert created.status_code == 201
    role = created.json()
    as_subject(client, "independent-approver")
    approved = client.post(f"/api/v1/authorization/roles/{role['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Role definition reviewed"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "Active"
    return approved.json()


def test_role_templates_require_independent_approval_and_explicit_permissions(client):
    as_subject(client)
    wildcard = client.post("/api/v1/authorization/roles", json={
        "role_code": "all.access", "name": "Wildcard role", "scope_type": "Organization",
        "permissions": ["*"]
    })
    assert wildcard.status_code == 422
    created = client.post("/api/v1/authorization/roles", json={
        "role_code": "finance.reviewer", "name": "Finance reviewer",
        "scope_type": "Organization", "permissions": ["invoice:read", "invoice:approve"]
    })
    assert created.status_code == 201
    row = created.json()
    assert row["status"] == "Proposed"
    assert client.post(f"/api/v1/authorization/roles/{row['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Self approval attempt"
    }).status_code == 403
    as_subject(client, "independent-approver")
    approved = client.post(f"/api/v1/authorization/roles/{row['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Role definition reviewed"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "Active"


def test_access_assignment_is_scoped_independently_reviewed_and_revocable(client):
    as_subject(client)
    role = create_active_role(client)
    as_subject(client, "requester")
    payload = {
        "role_template_id": role["id"], "subject": "employee-1",
        "scope_reference": "organization:org-a",
        "effective_from": datetime.now(timezone.utc).isoformat(),
        "effective_to": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "reason": "Temporary finance review responsibility"
    }
    bad_scope = {**payload, "scope_reference": "department:finance"}
    assert client.post("/api/v1/authorization/assignments", json=bad_scope).status_code == 422
    created = client.post("/api/v1/authorization/assignments", json=payload)
    assert created.status_code == 201
    row = created.json()
    assert row["status"] == "Pending Approval"
    assert client.post(f"/api/v1/authorization/assignments/{row['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Self review"
    }).status_code == 403

    as_subject(client, "independent-reviewer")
    approved = client.post(f"/api/v1/authorization/assignments/{row['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Access need verified"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    revoked = client.post(f"/api/v1/authorization/assignments/{row['id']}/revoke", json={
        "expected_version": 2, "reason": "Temporary access no longer required"
    })
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "Revoked"


def test_authorization_records_are_organization_scoped_and_permission_separated(client):
    as_subject(client)
    role = create_active_role(client)
    as_subject(client, "reader", {"authorization:role:read"})
    assert client.get("/api/v1/authorization/roles").status_code == 200
    assert client.post("/api/v1/authorization/roles", json={
        "role_code": "viewer", "name": "Viewer", "scope_type": "Organization",
        "permissions": ["invoice:read"]
    }).status_code == 403
    as_subject(client, "other-org", PERMS, org="org-b")
    assert client.get("/api/v1/authorization/roles").json() == []
