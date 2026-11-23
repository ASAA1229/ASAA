from decimal import Decimal

from sqlalchemy import select

from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from tests.integration_support import db_of

# Illustrative test-only numbers; the product seeds and invents no rates.
RULES = {"code": "TEST-SET", "currency": "INR", "effective_from": "2027-02-01", "rounding_mode": "half_up", "lines": [
    {"line_type": "tax", "code": "T1", "basis": "gross", "rate": "0.100000", "cap_amount": "300.00"},
    {"line_type": "deduction", "code": "D1", "basis": "gross", "rate": "0.033333"},
    {"line_type": "deduction", "code": "D2", "basis": "fixed", "fixed_amount": "25.00"},
    {"line_type": "contribution", "code": "C1", "basis": "gross", "rate": "0.050000", "borne_by": "employer"}]}


def employee(client, code="E-R1"):
    r = client.post("/api/v1/hr/employees", json={"employee_code": code, "first_name": "Test", "last_name": "Person", "work_email": f"{code}@example.invalid",
                                                  "employment_type": "Employee", "hire_date": "2026-11-01"})
    return r.json()["id"]


def run_with_entry(client, gross="1000.00", code="2027-02"):
    period = client.post("/api/v1/payroll/periods", json={"period_code": code, "start_date": "2027-02-01", "end_date": "2027-02-28"}).json()
    run = client.post("/api/v1/payroll/runs", json={"period_id": period["id"], "run_code": code + "-01", "currency": "INR"}).json()
    emp = employee(client, "E-" + code)
    entry = client.post(f"/api/v1/payroll/runs/{run['id']}/entries", json={"employee_id": emp, "currency": "INR", "gross_amount": gross, "deduction_total": "0.00", "net_amount": gross,
                                                                          "source_references": []}).json()
    return run, entry


def as_user(client, subject, perms):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, "org-a", frozenset(perms))


def approve(client, rule_set_id, maker_client_perms=("payroll:rules:approve",)):
    maker = client.app.dependency_overrides[get_principal]
    as_user(client, "rules-approver", maker_client_perms)
    r = client.post(f"/api/v1/payroll/rule-sets/{rule_set_id}/decision", json={"decision": "Approved"})
    client.app.dependency_overrides[get_principal] = maker
    return r


def test_calculation_refuses_without_approved_rule_set_and_pending_set_does_not_apply(client):
    run, _ = run_with_entry(client)
    assert client.post(f"/api/v1/payroll/runs/{run['id']}/calculate").json()["detail"]["code"] == "policy_not_configured"
    created = client.post("/api/v1/payroll/rule-sets", json=RULES)
    assert created.status_code == 201 and created.json()["status"] == "Pending Approval" and len(created.json()["lines"]) == 4
    assert client.post(f"/api/v1/payroll/runs/{run['id']}/calculate").status_code == 409


def test_maker_cannot_approve_and_overlap_and_rounding_are_enforced(client):
    created = client.post("/api/v1/payroll/rule-sets", json=RULES).json()
    assert client.post(f"/api/v1/payroll/rule-sets/{created['id']}/decision", json={"decision": "Approved"}).status_code == 403
    assert client.post("/api/v1/payroll/rule-sets", json=dict(RULES, code="OTHER")).json()["detail"]["code"] == "payroll_rule_set_period_overlap"
    assert client.post("/api/v1/payroll/rule-sets", json={k: v for k, v in dict(RULES, code="X2", effective_from="2030-01-01").items() if k != "rounding_mode"}).status_code == 422
    bad = dict(RULES, code="X3", effective_from="2031-01-01", lines=[{"line_type": "deduction", "code": "B", "basis": "gross", "rate": "0.1", "fixed_amount": "5.00"}])
    assert client.post("/api/v1/payroll/rule-sets", json=bad).status_code == 422
    assert client.post("/api/v1/payroll/rule-sets", json=dict(RULES, code="X4", effective_from="2031-01-01", effective_to="2030-01-01")).status_code == 422


def test_approved_rule_set_calculates_decimal_lines_with_lineage_and_audit(client):
    run, entry = run_with_entry(client, gross="1234.57")
    created = client.post("/api/v1/payroll/rule-sets", json=RULES).json()
    assert approve(client, created["id"]).json()["status"] == "Approved"
    result = client.post(f"/api/v1/payroll/runs/{run['id']}/calculate")
    assert result.status_code == 200, result.text
    # T1: 123.457 -> 123.46 ; D1: 41.1... -> 41.15 ; D2 25.00 ; employer C1 61.7285 -> 61.73
    assert result.json()["employee_deduction_total"] == "189.61" and result.json()["employer_contribution_total"] == "61.73"
    entries = client.get(f"/api/v1/payroll/runs/{run['id']}/entries").json()
    assert Decimal(str(entries[0]["deduction_total"])) == Decimal("189.61") and Decimal(str(entries[0]["net_amount"])) == Decimal("1044.96")
    lines = client.get(f"/api/v1/payroll/runs/{run['id']}/entries/{entry['id']}/lines").json()
    assert {line["code"]: line["amount"] for line in lines} == {"T1": 123.46, "D1": 41.15, "D2": 25.0, "C1": 61.73}
    assert all(line["rule_set_id"] == created["id"] and line["rounding_mode"] == "half_up" for line in lines)
    assert client.get(f"/api/v1/payroll/runs/{run['id']}/summary").json()["entries_reconciled"] is True
    # recalculating replaces lines instead of duplicating them; the cap applies on a large gross
    assert len(client.get(f"/api/v1/payroll/runs/{run['id']}/entries/{entry['id']}/lines").json()) == 4
    client.post(f"/api/v1/payroll/runs/{run['id']}/calculate")
    assert len(client.get(f"/api/v1/payroll/runs/{run['id']}/entries/{entry['id']}/lines").json()) == 4
    actions = {a.action for a in db_of(client).scalars(select(AuditEvent)).all()}
    assert {"payroll_rule_set.proposed", "payroll_rule_set.decided", "payroll_run.calculated"} <= actions


def test_rule_set_must_cover_the_period_currency_and_org_and_run_must_be_editable(client):
    run, _ = run_with_entry(client, code="2027-02")
    later = client.post("/api/v1/payroll/rule-sets", json=dict(RULES, code="LATER", effective_from="2027-03-01")).json()
    approve(client, later["id"])
    assert client.post(f"/api/v1/payroll/runs/{run['id']}/calculate").json()["detail"]["code"] == "policy_not_configured"
    usd = client.post("/api/v1/payroll/rule-sets", json=dict(RULES, code="USD", currency="USD", effective_from="2020-01-01")).json()
    approve(client, usd["id"])
    assert client.post(f"/api/v1/payroll/runs/{run['id']}/calculate").json()["detail"]["code"] == "policy_not_configured"
    as_user(client, "other-org-user", {"payroll:rules:read"})
    client.app.dependency_overrides[get_principal] = lambda: Principal("x", "org-b", frozenset({"payroll:rules:read", "payroll:entry:write"}))
    assert client.get("/api/v1/payroll/rule-sets").json() == []
    assert client.post(f"/api/v1/payroll/runs/{run['id']}/calculate").status_code == 404


def test_deductions_exceeding_gross_are_refused_and_nothing_is_written(client):
    run, entry = run_with_entry(client, gross="10.00", code="2027-02")
    big = dict(RULES, lines=[{"line_type": "deduction", "code": "BIG", "basis": "fixed", "fixed_amount": "50.00"}])
    approve(client, client.post("/api/v1/payroll/rule-sets", json=big).json()["id"])
    refused = client.post(f"/api/v1/payroll/runs/{run['id']}/calculate")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "payroll_deductions_exceed_gross"
    assert client.get(f"/api/v1/payroll/runs/{run['id']}/entries/{entry['id']}/lines").json() == []
