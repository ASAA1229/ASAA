from datetime import datetime, timezone

from asaa_ap.security import Principal, get_principal


ADMIN = {
    "organization:profile:read", "organization:profile:write",
    "organization:structure:read", "organization:structure:write", "organization:structure:approve",
    "identity:access-review:read", "identity:access-review:create",
    "identity:access-review:review", "audit:read",
}


def as_subject(client, subject="admin", permissions=None, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        subject, org, frozenset(ADMIN if permissions is None else permissions)
    )


def test_organization_profile_is_scoped_and_versioned(client):
    as_subject(client)
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
    as_subject(client)
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
    # The creator cannot approve their own proposed structure.
    assert client.post(f"/api/v1/administration/units/{root.json()['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Self approval attempt"
    }).status_code == 403

    as_subject(client, "independent-reviewer")
    assert client.post(f"/api/v1/administration/units/{child.json()['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Parent is not active"
    }).status_code == 409

    assert client.post(f"/api/v1/administration/units/{root.json()['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Legal entity structure reviewed"
    }).status_code == 200
    assert client.post(f"/api/v1/administration/units/{child.json()['id']}/review", json={
        "expected_version": 1, "decision": "Approve", "reason": "Department structure reviewed"
    }).status_code == 200
    assert len(client.get("/api/v1/administration/units").json()) == 2


def test_access_review_campaign_decisions_are_audited_and_not_self_reviewed(client):
    as_subject(client)
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
    campaign = client.get("/api/v1/administration/access-reviews").json()[0]
    assert campaign["status"] == "Completed"

    events = client.get("/api/v1/ap/audit-events").json()
    assert any(event["action"] == "identity_access_review.decided" for event in events)


def test_administration_permissions_are_separate(client):
    as_subject(client, "reader", {"organization:structure:read"})
    assert client.get("/api/v1/administration/units").status_code == 200
    assert client.post("/api/v1/administration/units", json={
        "unit_type": "Department", "unit_code": "dept", "name": "Department"
    }).status_code == 403

def test_organization_unit_updates_are_scoped_versioned_and_audited(client):
    as_subject(client)
    created = client.post("/api/v1/administration/units", json={
        "unit_type": "Department",
        "unit_code": "operations",
        "name": "Operations",
        "owner_subject": "manager-1",
        "effective_from": "2026-11-01",
    })
    assert created.status_code == 201
    unit = created.json()

    updated = client.patch(f"/api/v1/administration/units/{unit['id']}", json={
        "expected_version": 1,
        "name": "Operations & Delivery",
        "owner_subject": "manager-2",
        "effective_to": "2027-12-31",
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "Operations & Delivery"
    assert updated.json()["owner_subject"] == "manager-2"
    assert updated.json()["effective_to"] == "2027-12-31"
    assert updated.json()["version"] == 2

    stale = client.patch(f"/api/v1/administration/units/{unit['id']}", json={
        "expected_version": 1, "name": "Stale update"
    })
    assert stale.status_code == 409

    events = client.get("/api/v1/ap/audit-events").json()
    assert any(event["action"] == "organization_unit.updated" for event in events)

    as_subject(client, "other-org", org="org-b")
    assert client.patch(f"/api/v1/administration/units/{unit['id']}", json={
        "expected_version": 2, "name": "Cross-organization update"
    }).status_code == 404

    as_subject(client, "reader", {"organization:structure:read"})
    assert client.patch(f"/api/v1/administration/units/{unit['id']}", json={
        "expected_version": 2, "name": "Unauthorized update"
    }).status_code == 403
