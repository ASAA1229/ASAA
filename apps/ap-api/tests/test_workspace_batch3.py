"""Renewals, operations status, extra register field kinds and the finance report sections added for the remaining workspaces."""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

import asaa_ap.operations as operations
from asaa_ap.database import get_db
from asaa_ap.main import app
from asaa_ap.models import ARInvoice
from asaa_ap.security import Principal, get_principal
from asaa_registers.catalog import TYPES

FIN = {"ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:receipt:read", "ar:receipt:write",
       "ar:receipt:allocate", "expense:claim:read:all", "expense:claim:read", "expense:claim:write", "expense:claim:submit", "expense:claim:review"}
REG = {f"register:{t}:{a}" for t in TYPES for a in ("read", "write", "review")}


def as_p(client, subject="maker", perms=FIN | REG, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


@pytest.fixture
def db(client):
    session = next(app.dependency_overrides[get_db]())
    yield session
    session.close()


def make_invoice(client, customer, currency="INR", amount="100.00", due="2026-11-05"):
    inv = client.post("/api/v1/ar/invoices", json={"customer_id": customer, "currency": currency, "issue_date": "2026-11-01", "due_date": due,
                                                   "lines": [{"description": "Work", "quantity": "1", "unit_price": amount, "tax_amount": "0.00"}]}).json()
    return client.post(f"/api/v1/ar/invoices/{inv['id']}/issue", json={"expected_version": inv["version"], "reason": "Ready to issue"}).json()


def approve(client, rtype, record):
    sub = client.post(f"/api/v1/registers/{rtype}/{record['id']}/submit", json={"expected_version": record["version"]}).json()
    as_p(client, "checker")
    done = client.post(f"/api/v1/registers/{rtype}/{record['id']}/review", json={"expected_version": sub["version"], "decision": "Approve", "reason": "Reviewed"}).json()
    as_p(client)
    return done


# ---------------------------------------------------------------- contract renewals
def test_contract_renewals_lists_approved_contracts_due_soon_overdue_first(client):
    as_p(client)
    today = date.today()
    for code, offset in (("C-LATE", -5), ("C-SOON", 30), ("C-FAR", 400)):
        rec = client.post("/api/v1/registers/contract", json={"code": code, "title": f"Contract {code}", "data": {
            "counterparty": "Globex", "contract_type": "Customer", "renewal_date": (today + timedelta(days=offset)).isoformat()}}).json()
        if code != "C-FAR":
            approve(client, "contract", rec)
    client.post("/api/v1/registers/contract", json={"code": "C-DRAFT", "title": "Draft contract", "data": {"counterparty": "X", "contract_type": "Other", "renewal_date": today.isoformat()}})
    rows = client.get("/api/v1/registers/contract/renewals?within_days=90").json()
    assert [r["code"] for r in rows] == ["C-LATE", "C-SOON"]  # drafts and far-future renewals excluded
    assert rows[0]["days_until_renewal"] == -5 and rows[1]["days_until_renewal"] == 30
    assert client.get("/api/v1/registers/policy/renewals").status_code == 404
    as_p(client, "other", FIN | REG, org="org-b")
    assert client.get("/api/v1/registers/contract/renewals").json() == []
    as_p(client, "noaccess", set())
    assert client.get("/api/v1/registers/contract/renewals").status_code == 403


# ---------------------------------------------------------------- register field kinds
def test_money_currency_and_restricted_execution_mode_validation(client):
    as_p(client)
    ok = client.post("/api/v1/registers/budget", json={"code": "B-1", "title": "Marketing Q1", "data": {"fiscal_period": "2027-Q1", "currency": "INR", "planned_amount": "125000.50"}})
    assert ok.status_code == 201 and ok.json()["data"]["planned_amount"] == "125000.50"
    for bad in ({"planned_amount": "-1"}, {"planned_amount": "1.234"}, {"planned_amount": "abc"}, {"planned_amount": "NaN"}, {"currency": "inr"}, {"currency": "RUPEES"}):
        data = {"fiscal_period": "2027-Q1", "currency": "INR", "planned_amount": "10.00", **bad}
        assert client.post("/api/v1/registers/budget", json={"code": "B-X", "title": "Bad budget", "data": data}).status_code == 422, bad
    auto = {"trigger": "Invoice issued", "action": "Notify finance", "scope": "AR read-only", "stop_procedure": "Disable in registry"}
    assert client.post("/api/v1/registers/automation", json={"code": "A-1", "title": "Notify", "data": {**auto, "execution_mode": "Dry-run only"}}).status_code == 201
    live = client.post("/api/v1/registers/automation", json={"code": "A-2", "title": "Live", "data": {**auto, "execution_mode": "Live"}})
    assert live.status_code == 422  # live execution is not an option until separately authorized
    scenario = {"horizon": "12 months", "assumptions": "Flat demand"}
    assert client.post("/api/v1/registers/scenario", json={"code": "S-1", "title": "Base case", "data": scenario}).status_code == 422  # uncertainty must be disclosed
    assert client.post("/api/v1/registers/scenario", json={"code": "S-1", "title": "Base case", "data": {**scenario, "uncertainty_note": "Demand may fall 20%"}}).status_code == 201


# ---------------------------------------------------------------- reports: cash outlook / reconciliation / payroll accounting
def test_reconciliation_is_clean_for_consistent_data_and_flags_injected_inconsistencies(client, db):
    as_p(client)
    cust = client.post("/api/v1/ar/customers", json={"legal_name": "Initech"}).json()
    inv = make_invoice(client, cust["id"])
    rec = client.post("/api/v1/ar/receipts", json={"customer_id": cust["id"], "currency": "INR", "amount": "100.00", "received_date": "2026-11-06",
                                                   "allocations": [{"invoice_id": inv["id"], "amount": "100.00"}]})
    assert rec.status_code == 201, rec.text
    clean = client.get("/api/v1/reports/summary").json()["sections"]["reconciliation"]["data"]
    assert clean["exception_count"] == 0 and clean["unallocated_receipts_by_currency"] == {}
    unapplied = client.post("/api/v1/ar/receipts", json={"customer_id": cust["id"], "currency": "USD", "amount": "40.00", "received_date": "2026-11-06"})
    assert unapplied.status_code == 201
    data = client.get("/api/v1/reports/summary").json()["sections"]["reconciliation"]["data"]
    assert data["unallocated_receipts_by_currency"] == {"USD": "40.00"} and data["exceptions"][0]["type"] == "receipt_not_fully_allocated"
    row = db.get(ARInvoice, inv["id"])
    row.status = "Issued"  # simulate corruption: paid in allocations but status regressed
    db.commit()
    data = client.get("/api/v1/reports/summary").json()["sections"]["reconciliation"]["data"]
    assert "issued_invoice_has_allocations" in {e["type"] for e in data["exceptions"]}
    assert "bank" in data["note"].lower()


def test_cash_outlook_is_per_currency_derived_and_labelled_not_a_bank_balance(client):
    as_p(client)
    cust = client.post("/api/v1/ar/customers", json={"legal_name": "Initech"}).json()
    make_invoice(client, cust["id"], "INR", "100.00", "2026-12-10")
    make_invoice(client, cust["id"], "USD", "50.00", "2027-01-15")
    section = client.get("/api/v1/reports/summary").json()["sections"]["cash_outlook"]
    inflow = section["data"]["expected_receipts_by_currency_and_due_month"]
    assert inflow == {"INR": {"2026-12": "100.00"}, "USD": {"2027-01": "50.00"}}
    assert "NOT a bank balance" in section["data"]["note"]
    as_p(client, "reader", {"ar:invoice:read"})
    assert "cash_outlook" not in client.get("/api/v1/reports/summary").json()["sections"]  # needs expense visibility too


def test_payroll_accounting_requires_its_own_permission_and_exposes_only_totals(client):
    as_p(client, "hr", {"payroll:read", "payroll:compensation:read", "hr:employee:read"})
    assert "payroll_accounting" not in client.get("/api/v1/reports/summary").json()["sections"]
    as_p(client, "finance", {"payroll:accounting:read"})
    section = client.get("/api/v1/reports/summary").json()["sections"]["payroll_accounting"]
    assert section["data"]["closed_run_totals_by_currency"] == {} and "No journal posting" in section["data"]["note"]


# ---------------------------------------------------------------- operations
def test_backup_status_reads_the_scheduler_status_file_and_requires_permission(client, tmp_path, monkeypatch):
    as_p(client, "ops", {"ops:backup:read", "ops:status:read"})
    from types import SimpleNamespace
    cfg = SimpleNamespace(backup_dir=None, backup_max_age_hours=26)
    monkeypatch.setattr(operations, "get_settings", lambda: cfg)
    assert client.get("/api/v1/operations/backup-status").json()["configured"] is False
    cfg.backup_dir = str(tmp_path)
    assert client.get("/api/v1/operations/backup-status").json()["reason"] == "no backup status recorded"
    (tmp_path / "asaa-1.sqlite.enc").write_bytes(b"x")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    (tmp_path / "backup-status.json").write_text(json.dumps({"last_success_at": now.isoformat(), "last_artifact": "asaa-1.sqlite.enc"}))
    assert client.get("/api/v1/operations/backup-status").json()["ok"] is True
    (tmp_path / "backup-status.json").write_text(json.dumps({"last_success_at": (now - timedelta(hours=40)).isoformat(), "last_artifact": "asaa-1.sqlite.enc"}))
    stale = client.get("/api/v1/operations/backup-status").json()
    assert stale["ok"] is False and "old" in stale["reason"]
    (tmp_path / "backup-status.json").write_text(json.dumps({"last_success_at": (now - timedelta(hours=2)).isoformat(), "last_failure_at": now.isoformat(), "last_artifact": "asaa-1.sqlite.enc"}))
    assert client.get("/api/v1/operations/backup-status").json()["reason"] == "last backup run failed"
    as_p(client, "nobody", set())
    assert client.get("/api/v1/operations/backup-status").status_code == 403


def test_platform_status_reports_flags_without_secrets(client):
    as_p(client, "ops", {"ops:status:read"})
    body = client.get("/api/v1/operations/status").json()
    assert body["database"] == "available" and set(body) >= {"environment", "identity_provider", "notification_provider", "backup_configured", "oidc_issuer_configured"}
    text = json.dumps(body).lower()
    assert "password" not in text and "secret" not in text and "token" not in text.replace("notification", "")
    as_p(client, "nobody", set())
    assert client.get("/api/v1/operations/status").status_code == 403
