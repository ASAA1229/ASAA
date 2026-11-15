"""Reporting aggregates (read-only, permission-filtered, no payroll) and audit trail filters."""
from asaa_ap.security import Principal, get_principal


def as_p(client, subject="u", perms=(), org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


ALL = {"supplier:read", "supplier:write", "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:receipt:read",
       "hr:employee:read", "hr:employee:write", "hr:leave:read", "expense:claim:read:all", "expense:claim:read", "expense:claim:write", "audit:read",
       "payroll:compensation:write", "payroll:compensation:read", "tms:timesheet:read:all", "register:policy:read", "register:policy:write",
       "procurement:request:read:all"}


def seed(client):
    as_p(client, "maker", ALL)
    assert client.post("/api/v1/ap/suppliers", json={"legal_name": "Globex"}).status_code == 201
    cust = client.post("/api/v1/ar/customers", json={"legal_name": "Initech"}).json()
    for currency, qty in (("INR", "100.00"), ("USD", "50.00")):
        inv = client.post("/api/v1/ar/invoices", json={"customer_id": cust["id"], "currency": currency, "issue_date": "2026-11-01", "due_date": "2026-11-05",
                                                       "lines": [{"description": "Work", "quantity": "1", "unit_price": qty, "tax_amount": "0.00"}]})
        assert inv.status_code == 201, inv.text
        issued = client.post(f"/api/v1/ar/invoices/{inv.json()['id']}/issue", json={"expected_version": inv.json()["version"], "reason": "Ready to issue"})
        assert issued.status_code == 200, issued.text
    emp = client.post("/api/v1/hr/employees", json={"first_name": "Asha", "last_name": "Rao", "employment_type": "Employee"}).json()
    client.post("/api/v1/payroll/compensation", json={"employee_id": emp["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "987654.00",
                                                       "frequency": "Monthly", "effective_from": "2026-12-01"})
    client.post("/api/v1/registers/policy", json={"code": "POL-1", "title": "Policy one", "data": {"document_type": "Policy"}})


def test_summary_aggregates_per_currency_with_lineage_and_freshness(client):
    seed(client)
    body = client.get("/api/v1/reports/summary").json()
    assert body["generated_at"] and "never converted" in body["currency_note"]
    ar = body["sections"]["receivables"]
    assert ar["data"]["outstanding_by_currency"] == {"INR": "100.00", "USD": "50.00"}  # per currency, never mixed
    assert ar["data"]["invoices_by_status"] == {"Issued": 2} and ar["data"]["overdue_invoices"] == 2
    assert ar["sources"] == ["ar_invoices", "ar_receipt_allocations"]
    assert body["sections"]["suppliers"]["data"]["suppliers_by_status"] == {"Draft": 1}
    assert body["sections"]["workforce"]["data"]["employees_by_status"]
    assert body["sections"]["registers"]["data"]["by_register"]["policy"] == {"Draft": 1}


def test_summary_never_exposes_payroll_or_salary_figures(client):
    seed(client)
    text = client.get("/api/v1/reports/summary").text
    assert "987654" not in text and "gross" not in text.lower() and "salary" not in text.lower()


def test_sections_follow_the_callers_permissions_and_organization(client):
    seed(client)
    as_p(client, "reader", {"supplier:read"})
    assert list(client.get("/api/v1/reports/summary").json()["sections"]) == ["suppliers"]
    as_p(client, "nobody", set())
    assert client.get("/api/v1/reports/summary").json()["sections"] == {}
    as_p(client, "other", ALL, org="org-b")
    other = client.get("/api/v1/reports/summary").json()["sections"]
    assert other["receivables"]["data"]["invoices_by_status"] == {} and other["suppliers"]["data"]["suppliers_by_status"] == {}
    client.app.dependency_overrides.pop(get_principal)
    assert client.get("/api/v1/reports/summary").status_code in (401, 503)


def test_audit_trail_filters_by_action_actor_and_entity_and_stays_org_scoped(client):
    seed(client)
    as_p(client, "auditor", {"audit:read"})
    everything = client.get("/api/v1/ap/audit-events").json()
    assert len(everything) >= 6
    assert all(e["action"].startswith("supplier.") for e in client.get("/api/v1/ap/audit-events?action=supplier.").json())
    assert {e["actor_id"] for e in client.get("/api/v1/ap/audit-events?actor_id=maker").json()} == {"maker"}
    assert client.get("/api/v1/ap/audit-events?actor_id=nobody").json() == []
    assert all(e["entity_type"] == "register:policy" for e in client.get("/api/v1/ap/audit-events?entity_type=register:policy").json())
    assert client.get("/api/v1/ap/audit-events?outcome=maybe").status_code == 422
    assert client.get("/api/v1/ap/audit-events?action=%25").json() == []  # LIKE wildcards are escaped, not interpreted
    as_p(client, "other-auditor", {"audit:read"}, org="org-b")
    assert client.get("/api/v1/ap/audit-events").json() == []
