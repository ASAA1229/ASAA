from datetime import date
from asaa_ap.security import get_principal, Principal


def create_customer(client, name="Example Customer Ltd"):
    response = client.post("/api/v1/ar/customers", json={
        "legal_name": name, "email": "billing@example.test", "customer_code": "CUST-001"
    })
    assert response.status_code == 201
    return response.json()


def create_invoice(client, customer_id):
    response = client.post("/api/v1/ar/invoices", json={
        "customer_id": customer_id, "invoice_number": "INV-001", "currency": "USD",
        "issue_date": "2026-11-01", "due_date": "2026-11-30",
        "lines": [{"description": "Implementation services", "quantity": "2", "unit_price": "50.00", "tax_amount": "10.00"}]
    })
    assert response.status_code == 201
    return response.json()


def test_customer_duplicate_detection(client):
    create_customer(client)
    duplicate = client.post("/api/v1/ar/customers", json={
        "legal_name": "  EXAMPLE CUSTOMER LTD ", "email": "another@example.test"
    })
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "possible_duplicate_customer"


def test_invoice_draft_issue_and_partial_receipt_allocation(client):
    customer = create_customer(client)
    invoice = create_invoice(client, customer["id"])
    assert invoice["status"] == "Draft"
    assert str(invoice["total"]) == "110.00"
    issued = client.post(f"/api/v1/ar/invoices/{invoice['id']}/issue", json={
        "expected_version": invoice["version"], "reason": "Approved customer milestone"
    })
    assert issued.status_code == 200
    receipt = client.post("/api/v1/ar/receipts", json={
        "customer_id": customer["id"], "currency": "USD", "amount": "40.00",
        "received_date": "2026-11-12", "reference": "BANK-REF-1",
        "allocations": [{"invoice_id": invoice["id"], "amount": "40.00"}]
    })
    assert receipt.status_code == 201
    assert str(receipt.json()["applied_amount"]) == "40.00"
    current = client.get(f"/api/v1/ar/invoices/{invoice['id']}").json()
    assert current["status"] == "Partially Paid"
    assert str(current["outstanding"]) == "70.00"


def test_receipt_cannot_overallocate_invoice(client):
    customer = create_customer(client)
    invoice = create_invoice(client, customer["id"])
    client.post(f"/api/v1/ar/invoices/{invoice['id']}/issue", json={
        "expected_version": 1, "reason": "Approved"
    })
    response = client.post("/api/v1/ar/receipts", json={
        "customer_id": customer["id"], "currency": "USD", "amount": "120.00",
        "received_date": "2026-11-12",
        "allocations": [{"invoice_id": invoice["id"], "amount": "120.00"}]
    })
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "allocation_exceeds_outstanding"


def test_invoice_and_customer_are_organization_scoped(client):
    customer = create_customer(client)
    invoice = create_invoice(client, customer["id"])
    client.app.dependency_overrides[get_principal] = lambda: Principal("other", "org-b", frozenset({"ar:customer:read", "ar:invoice:read"}))
    assert client.get(f"/api/v1/ar/customers/{customer['id']}").status_code == 404
    assert client.get(f"/api/v1/ar/invoices/{invoice['id']}").status_code == 404


def test_ar_requires_explicit_permissions(client):
    client.app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-a", frozenset({"ar:customer:read"}))
    response = client.post("/api/v1/ar/customers", json={"legal_name": "No Write Permission Ltd"})
    assert response.status_code == 403
