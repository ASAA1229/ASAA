from datetime import date, timedelta


def payload(title="Office equipment"):
    return {
        "title": title,
        "purpose": "Replace essential work equipment",
        "needed_by": (date.today() + timedelta(days=30)).isoformat(),
        "currency": "INR",
        "cost_center": "ADMIN",
        "lines": [
            {"description": "Laptop docking station", "quantity": "2", "unit_of_measure": "each", "estimated_unit_cost": "4500.00"},
            {"description": "USB-C cable", "quantity": "3", "unit_of_measure": "each", "estimated_unit_cost": "500.00"},
        ],
    }


def test_create_purchase_request_calculates_totals_and_audits(client):
    response = client.post("/api/v1/ap/purchase-requests", json=payload())
    assert response.status_code == 201
    row = response.json()
    assert row["status"] == "Draft"
    assert row["currency"] == "INR"
    assert row["estimated_total"] == "10500.00"
    assert len(row["lines"]) == 2
    events = client.get("/api/v1/ap/audit-events").json()
    assert any(event["action"] == "purchase_request.created" for event in events)


def test_purchase_request_submit_and_independent_approval(client):
    created = client.post("/api/v1/ap/purchase-requests", json=payload()).json()
    submitted = client.post(
        f"/api/v1/ap/purchase-requests/{created['id']}/submit",
        json={"expected_version": created["version"], "reason": "Ready for review"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "Submitted"

    from asaa_ap.security import Principal, get_principal
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "reviewer", "org-a", frozenset({
            "procurement:request:read", "procurement:request:read:all", "procurement:request:review"
        })
    )
    reviewed = client.post(
        f"/api/v1/ap/purchase-requests/{created['id']}/review",
        json={"expected_version": submitted.json()["version"], "decision": "approve", "reason": "Within approved need"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"
    assert reviewed.json()["reviewed_by"] == "reviewer"


def test_requester_cannot_approve_own_purchase_request(client):
    created = client.post("/api/v1/ap/purchase-requests", json=payload()).json()
    submitted = client.post(
        f"/api/v1/ap/purchase-requests/{created['id']}/submit",
        json={"expected_version": created["version"], "reason": "Submit for review"},
    ).json()
    response = client.post(
        f"/api/v1/ap/purchase-requests/{created['id']}/review",
        json={"expected_version": submitted["version"], "decision": "approve", "reason": "Self approval"},
    )
    assert response.status_code == 403


def test_purchase_request_is_organization_scoped(client):
    created = client.post("/api/v1/ap/purchase-requests", json=payload()).json()
    from asaa_ap.security import Principal, get_principal
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "other", "org-b", frozenset({"procurement:request:read", "procurement:request:read:all"})
    )
    response = client.get(f"/api/v1/ap/purchase-requests/{created['id']}")
    assert response.status_code == 404


def test_purchase_request_rejects_invalid_lines_and_currency(client):
    invalid = payload()
    invalid["lines"][0]["quantity"] = "0"
    assert client.post("/api/v1/ap/purchase-requests", json=invalid).status_code == 422
    invalid = payload()
    invalid["currency"] = "INR1"
    assert client.post("/api/v1/ap/purchase-requests", json=invalid).status_code == 422


def test_purchase_request_requires_permissions(client):
    from asaa_ap.security import Principal, get_principal
    client.app.dependency_overrides[get_principal] = lambda: Principal("limited", "org-a", frozenset())
    assert client.post("/api/v1/ap/purchase-requests", json=payload()).status_code == 403
