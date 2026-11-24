from asaa_ap.security import Principal, get_principal
from tests.test_ar import create_customer, create_invoice

ALL = {"ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:invoice:void", "ar:receipt:read", "ar:receipt:write", "ar:receipt:allocate",
       "ar:debit:write", "ar:debit:read", "ar:debit:approve", "ar:refund:write", "ar:refund:read", "ar:refund:approve", "ar:refund:record",
       "ar:dispute:write", "ar:dispute:read", "ar:dispute:resolve", "ar:credit:write", "ar:credit:read", "ar:credit:approve"}


def as_user(client, subject, perms=ALL, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


def issued_invoice(client):
    as_user(client, "maker")
    customer = create_customer(client)
    inv = create_invoice(client, customer["id"])
    client.post(f"/api/v1/ar/invoices/{inv['id']}/issue", json={"expected_version": inv["version"], "reason": "Approved milestone"})
    return customer, inv


def outstanding(client, invoice_id):
    return client.get(f"/api/v1/ar/invoices/{invoice_id}").json()["outstanding"]


def test_debit_note_maker_checker_grows_balance_and_flows_to_aging_and_statement(client):
    customer, inv = issued_invoice(client)
    note = client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv["id"], "amount": "25.00", "reason": "Late delivery charge"}).json()
    assert note["status"] == "Pending Approval" and float(outstanding(client, inv["id"])) == 110.0
    assert client.post(f"/api/v1/ar/debit-notes/{note['id']}/review", json={"decision": "approve", "reason": "self"}).status_code == 403
    as_user(client, "checker")
    assert client.post(f"/api/v1/ar/debit-notes/{note['id']}/review", json={"decision": "approve", "reason": "Verified"}).json()["status"] == "Approved"
    assert client.post(f"/api/v1/ar/debit-notes/{note['id']}/review", json={"decision": "approve", "reason": "again"}).status_code == 409
    body = client.get(f"/api/v1/ar/invoices/{inv['id']}").json()
    assert float(body["outstanding"]) == 135.0 and float(body["amount_debited"]) == 25.0 and body["status"] == "Issued"
    assert client.get("/api/v1/ar/aging?as_of=2026-12-15").json()["by_currency"]["USD"]["total"] == "135.00"
    assert client.get(f"/api/v1/ar/customers/{customer['id']}/statement").json()["closing_balance_by_currency"]["USD"] == "135.00"
    assert client.post(f"/api/v1/ar/invoices/{inv['id']}/void", json={"reason": "no longer valid"}).status_code == 409  # has a debit
    as_user(client, "other", org="org-b")
    assert client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv["id"], "amount": "1.00", "reason": "x-org"}).status_code == 404
    assert client.get("/api/v1/ar/debit-notes").json() == []
    as_user(client, "reader", {"ar:debit:read"})
    assert client.post("/api/v1/ar/debit-notes", json={"invoice_id": inv["id"], "amount": "1.00", "reason": "no perm"}).status_code == 403


def test_refund_reserves_unapplied_receipt_and_needs_three_distinct_people(client):
    customer, inv = issued_invoice(client)
    receipt = client.post("/api/v1/ar/receipts", json={"customer_id": customer["id"], "currency": "USD", "amount": "160.00", "received_date": "2026-11-05", "reference": "R-1",
                                                       "allocations": [{"invoice_id": inv["id"], "amount": "110.00"}]})
    assert receipt.status_code == 201, receipt.text
    rid = receipt.json()["id"]
    assert client.post("/api/v1/ar/refunds", json={"receipt_id": rid, "amount": "50.01", "reason": "Overpayment"}).json()["detail"]["code"] == "refund_exceeds_unapplied_receipt"
    refund = client.post("/api/v1/ar/refunds", json={"receipt_id": rid, "amount": "40.00", "reason": "Overpayment"}).json()
    assert client.post("/api/v1/ar/refunds", json={"receipt_id": rid, "amount": "10.01", "reason": "Too much"}).status_code == 409  # 40 is reserved
    assert client.post(f"/api/v1/ar/refunds/{refund['id']}/review", json={"decision": "approve", "reason": "self"}).status_code == 403
    assert client.post(f"/api/v1/ar/refunds/{refund['id']}/record-payment", json={"payment_reference": "BANK-1"}).status_code == 409  # not approved yet
    as_user(client, "approver")
    assert client.post(f"/api/v1/ar/refunds/{refund['id']}/review", json={"decision": "approve", "reason": "Verified"}).json()["status"] == "Approved"
    assert client.post(f"/api/v1/ar/refunds/{refund['id']}/record-payment", json={"payment_reference": "BANK-1"}).status_code == 403  # approver cannot also pay out
    as_user(client, "payer")
    done = client.post(f"/api/v1/ar/refunds/{refund['id']}/record-payment", json={"payment_reference": "BANK-1"})
    assert done.status_code == 200 and done.json()["status"] == "Refunded"
    stmt = client.get(f"/api/v1/ar/customers/{customer['id']}/statement").json()
    assert any(e["type"] == "refund" for e in stmt["entries"])
    as_user(client, "maker")
    rejected = client.post("/api/v1/ar/refunds", json={"receipt_id": rid, "amount": "10.00", "reason": "Second"}).json()
    as_user(client, "approver")
    client.post(f"/api/v1/ar/refunds/{rejected['id']}/review", json={"decision": "reject", "reason": "Nope"})
    as_user(client, "maker")
    assert client.post("/api/v1/ar/refunds", json={"receipt_id": rid, "amount": "10.00", "reason": "Retry"}).status_code == 201  # rejection released the reservation


def test_dispute_lifecycle_never_changes_balance_and_is_scoped(client):
    customer, inv = issued_invoice(client)
    assert client.post("/api/v1/ar/disputes", json={"invoice_id": inv["id"], "disputed_amount": "999.00", "reason": "Too much"}).status_code == 409
    d = client.post("/api/v1/ar/disputes", json={"invoice_id": inv["id"], "disputed_amount": "50.00", "reason": "Service not delivered"}).json()
    assert d["status"] == "Open"
    assert client.post(f"/api/v1/ar/disputes/{d['id']}/resolve", json={"outcome": "Rejected", "note": "self resolve"}).status_code == 403
    as_user(client, "resolver")
    assert client.post(f"/api/v1/ar/disputes/{d['id']}/resolve", json={"outcome": "Rejected", "note": "xxx", "credit_note_id": "n"}).status_code == 409
    resolved = client.post(f"/api/v1/ar/disputes/{d['id']}/resolve", json={"outcome": "Upheld", "note": "Credit to follow"})
    assert resolved.json()["status"] == "Upheld" and float(outstanding(client, inv["id"])) == 110.0
    assert client.post(f"/api/v1/ar/disputes/{d['id']}/resolve", json={"outcome": "Upheld", "note": "again"}).status_code == 409
    as_user(client, "maker")
    d2 = client.post("/api/v1/ar/disputes", json={"invoice_id": inv["id"], "disputed_amount": "10.00", "reason": "Wrong rate"}).json()
    assert client.post(f"/api/v1/ar/disputes/{d2['id']}/withdraw").json()["status"] == "Withdrawn"
    assert [x["status"] for x in client.get("/api/v1/ar/disputes?status=Open").json()] == []
    as_user(client, "other", org="org-b")
    assert client.get("/api/v1/ar/disputes").json() == []
    assert client.post(f"/api/v1/ar/disputes/{d['id']}/withdraw").status_code == 404
