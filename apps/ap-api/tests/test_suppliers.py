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



def test_supplier_identity_change_requires_reverification(client):
    supplier = client.post("/api/v1/ap/suppliers", json=create_payload()).json()
    pending = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 1, "status": "Pending Verification", "reason": "Evidence received"}).json()
    active = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": pending["version"], "status": "Active", "reason": "Verified"}).json()
    changed = client.patch(f"/api/v1/ap/suppliers/{supplier['id']}", json={"expected_version": active["version"], "legal_name": "Example Supplies Holdings Ltd"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "Pending Verification"
    audit = client.get("/api/v1/ap/audit-events").json()
    assert any(event["details"].get("reverification_required") for event in audit)


def test_supplier_code_conflict_on_update_is_a_conflict_not_server_error(client):
    first = client.post("/api/v1/ap/suppliers", json={"legal_name": "First Supplier", "supplier_code": "SUP-001"}).json()
    second = client.post("/api/v1/ap/suppliers", json={"legal_name": "Second Supplier", "supplier_code": "SUP-002"}).json()
    response = client.patch(f"/api/v1/ap/suppliers/{second['id']}", json={"expected_version": 1, "supplier_code": first["supplier_code"]})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "supplier_conflict"


def test_invalid_email_is_rejected(client):
    response = client.post("/api/v1/ap/suppliers", json={"legal_name": "Invalid Contact Supplier", "email": "not-an-email"})
    assert response.status_code == 422
