from fastapi.testclient import TestClient
from asaa_ap.main import app
from asaa_ap.security import get_principal, Principal


def test_missing_permission_is_denied(client):
    app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-a", frozenset({"supplier:read"}))
    response = client.post("/api/v1/ap/suppliers", json={"legal_name": "Restricted Supplier"})
    assert response.status_code == 403
