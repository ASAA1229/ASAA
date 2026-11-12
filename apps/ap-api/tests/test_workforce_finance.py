from datetime import date
from decimal import Decimal
from asaa_ap.main import app
from asaa_ap.security import get_principal, Principal

def test_timesheet_submission_and_independent_review(client):
    created = client.post("/api/v1/workforce-finance/timesheets", json={
        "period_start":"2026-11-01","period_end":"2026-11-07",
        "entries":[{"work_date":"2026-11-02","description":"Implementation","hours":"7.50","billable":True}]
    })
    assert created.status_code == 201
    row = created.json()
    assert row["total_hours"] == "7.50"
    submitted = client.post(f"/api/v1/workforce-finance/timesheets/{row['id']}/submit",
        json={"reason":"Week complete","expected_version":1})
    assert submitted.status_code == 200
    app.dependency_overrides[get_principal] = lambda: Principal("reviewer", "org-a", frozenset({"tms:timesheet:review", "expense:claim:review", "expense:claim:reimburse"}))
    reviewed = client.post(f"/api/v1/workforce-finance/timesheets/{row['id']}/review",
        json={"decision":"approve","reason":"Reviewed","expected_version":2})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"

def test_expense_claim_approval_and_reimbursement_are_separate(client):
    created = client.post("/api/v1/workforce-finance/expenses", json={
        "expense_date":"2026-11-04","category_code":"TRAVEL","description":"Local travel",
        "amount":"450.00","currency":"inr","receipt_reference":"docs/receipt-1"
    })
    assert created.status_code == 201
    row = created.json()
    assert row["currency"] == "INR"
    submitted = client.post(f"/api/v1/workforce-finance/expenses/{row['id']}/submit",
        json={"reason":"Claim complete","expected_version":1})
    assert submitted.status_code == 200
    app.dependency_overrides[get_principal] = lambda: Principal("reviewer", "org-a", frozenset({"tms:timesheet:review", "expense:claim:review", "expense:claim:reimburse"}))
    reviewed = client.post(f"/api/v1/workforce-finance/expenses/{row['id']}/review",
        json={"decision":"approve","reason":"Evidence checked","expected_version":2})
    assert reviewed.status_code == 200
    reimbursed = client.post(f"/api/v1/workforce-finance/expenses/{row['id']}/reimburse",
        json={"reimbursement_reference":"PAY-REF-1","expected_version":3})
    assert reimbursed.status_code == 200
    assert reimbursed.json()["status"] == "Reimbursement Recorded"

def test_timesheet_rejects_entries_outside_period(client):
    response = client.post("/api/v1/workforce-finance/timesheets", json={
        "period_start":"2026-11-01","period_end":"2026-11-07",
        "entries":[{"work_date":"2026-11-08","description":"Outside period","hours":"1.00"}]
    })
    assert response.status_code == 422
