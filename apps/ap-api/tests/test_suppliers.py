def create_payload(name="Example Supplies Ltd"):
    return {"legal_name": name, "email": "accounts@example.test", "category": "Services"}


def test_create_supplier_defaults_to_draft_and_audits(client):
    response = client.post("/api/v1/ap/suppliers", json=create_payload())
    assert response.status_code == 201
    supplier = response.json()
    assert supplier["status"] == "Draft"
    assert supplier["version"] == 1
    events = client.get("/api/v1/ap/audit-events").json()
    assert len(events) == 1
    assert events[0]["action"] == "supplier.created"


def test_duplicate_supplier_is_rejected_with_match(client):
    assert client.post("/api/v1/ap/suppliers", json=create_payload()).status_code == 201
    response = client.post("/api/v1/ap/suppliers", json=create_payload("  EXAMPLE   SUPPLIES LTD "))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "possible_duplicate_supplier"


def test_supplier_updates_require_expected_version(client):
    supplier = client.post("/api/v1/ap/suppliers", json=create_payload()).json()
    response = client.patch(f"/api/v1/ap/suppliers/{supplier['id']}", json={"expected_version": 1, "phone": "+1-555-0100"})
    assert response.status_code == 200
    assert response.json()["version"] == 2
    stale = client.patch(f"/api/v1/ap/suppliers/{supplier['id']}", json={"expected_version": 1, "phone": "+1-555-0101"})
    assert stale.status_code == 409


def test_status_lifecycle_and_verification_audit(client):
    supplier = client.post("/api/v1/ap/suppliers", json=create_payload()).json()
    pending = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 1, "status": "Pending Verification", "reason": "Documents submitted"})
    assert pending.status_code == 200
    active = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 2, "status": "Active", "reason": "Verification completed"})
    assert active.status_code == 200
    invalid = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 3, "status": "Draft", "reason": "Backwards transition"})
    assert invalid.status_code == 409
    actions = [event["action"] for event in client.get("/api/v1/ap/audit-events").json()]
    assert actions.count("supplier.status_changed") == 2


def test_supplier_data_is_organization_scoped(client):
    supplier = client.post("/api/v1/ap/suppliers", json=create_payload()).json()
    from asaa_ap.security import get_principal, Principal
    client.app.dependency_overrides[get_principal] = lambda: Principal("other", "org-b", frozenset({"supplier:read"}))
    assert client.get(f"/api/v1/ap/suppliers/{supplier['id']}").status_code == 404
