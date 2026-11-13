from datetime import datetime, timezone

from asaa_ap.security import Principal, get_principal


ADMIN = {
    "organization:profile:read", "organization:profile:write",
    "organization:structure:read", "organization:structure:write",
    "identity:access-review:read", "identity:access-review:create",
    "identity:access-review:review", "audit:read",
}


def as_subject(client, subject="admin", permissions=None, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        subject, org, frozenset(ADMIN if permissions is None else permissions)
    )


def test_organization_profile_is_scoped_and_versioned(client):
    created = client.put("/api/v1/administration/profile", json={
        "display_name": "ASAA", "lifecycle_status": "Pre-Incorporation"
    })
    assert created.status_code == 200
    assert created.json()["lifecycle_status"] == "Pre-Incorporation"
    assert client.put("/api/v1/administration/profile", json={
        "display_name": "Duplicate"
    }).status_code == 409

    updated = client.patch("/api/v1/administration/profile", json={
        "expected_version": 1, "website": "https://example.invalid"
    })
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["display_name"] == "ASAA"
    assert client.patch("/api/v1/administration/profile", json={
        "expected_version": 1, "display_name": "Stale"
    }).status_code == 409

    as_subject(client, "other-org", org="org-b")
    assert client.get("/api/v1/administration/profile").json() is None


def test_organization_structure_parent_validation_and_lifecycle(client):
    root = client.post("/api/v1/administration/units", json={
        "unit_type": "Legal Entity", "unit_code": "entity-main", "name": "Proposed entity"
    })
    assert root.status_code == 201
    assert root.json()["status"] == "Proposed"

    child = client.post("/api/v1/administration/units", json={
        "parent_id": root.json()["id"], "unit_type": "Department",
        "unit_code": "finance", "name": "Finance"
    })
    assert child.status_code == 201
    assert client.patch(f"/api/v1/administration/units/{child.json()['id']}", json={
        "expected_version": 1, "status": "Active"
    }).status_code == 409

    assert client.patch(f"/api/v1/administration/units/{root.json()['id']}", json={
        "expected_version": 1, "status": "Active"
    }).status_code == 200
    assert client.patch(f"/api/v1/administration/units/{child.json()['id']}", json={
        "expected_version": 1, "status": "Active"
    }).status_code == 200

    assert client.patch(f"/api/v1/administration/units/{root.json()['id']}", json={
        "expected_version": 2, "status": "Inactive"
    }).status_code == 409
    assert len(client.get("/api/v1/administration/units").json()) == 2


def test_access_review_campaign_decisions_are_audited_and_not_self_reviewed(client):
    created = client.post("/api/v1/administration/access-reviews", json={
        "title": "Quarterly access review",
        "source_reference": "identity-export:2026-Q4",
        "snapshot_as_of": datetime.now(timezone.utc).isoformat(),
        "items": [{
            "subject": "employee-1", "role_code": "finance-reviewer",
            "permission_snapshot": ["invoice:read", "invoice:approve"],
            "scope_reference": "organization:org-a",
            "justification": "Finance review responsibility"
        }]
    })
    assert created.status_code == 201
    item = created.json()["items"][0]

    as_subject(client, "employee-1")
    assert client.post(f"/api/v1/administration/access-reviews/items/{item['id']}/decision", json={
        "expected_version": 1, "decision": "Retain", "reason": "Self-review attempt"
    }).status_code == 403

    as_subject(client, "independent-reviewer")
    reviewed = client.post(f"/api/v1/administration/access-reviews/items/{item['id']}/decision", json={
        "expected_version": 1, "decision": "Modify", "reason": "Reduce scope to invoice read"
    })
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "Modify"
    assert reviewed.json()["reviewed_by"] == "independent-reviewer"

    events = client.get("/api/v1/ap/audit-events").json()
    assert any(event["action"] == "identity_access_review.decided" for event in events)


def test_administration_permissions_are_separate(client):
    as_subject(client, "reader", {"organization:structure:read"})
    assert client.get("/api/v1/administration/units").status_code == 200
    assert client.post("/api/v1/administration/units", json={
        "unit_type": "Department", "unit_code": "dept", "name": "Department"
    }).status_code == 403
