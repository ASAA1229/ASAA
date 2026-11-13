import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from asaa_ap.database import SessionLocal, engine, get_db
from asaa_ap.main import app
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal


POSTGRES_URL = os.getenv("ASAA_AP_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="PostgreSQL integration test requires ASAA_AP_POSTGRES_TEST_URL",
)


@pytest.fixture(scope="module")
def postgres_client():
    if os.getenv("ASAA_AP_DATABASE_URL") != POSTGRES_URL:
        pytest.fail("API engine and PostgreSQL test URL must target the same database")

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "postgres-integration-tester",
        "postgres-integration-org",
        frozenset({
            "hr:employee:write", "hr:employee:read", "hr:employment:write",
            "payroll:compensation:write", "payroll:compensation:read",
            "payroll:period:write", "payroll:run:write",
            "payroll:entry:write", "payroll:read",
        }),
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_postgresql_readiness_and_people_payroll_round_trip(postgres_client):
    revision_columns = inspect(engine).get_columns("alembic_version")
    assert next(column for column in revision_columns if column["name"] == "version_num")["type"].length >= 128

    ready = postgres_client.get("/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "database": "available"}

    suffix = uuid4().hex[:10]
    employee_response = postgres_client.post("/api/v1/hr/employees", json={
        "employee_code": f"PG-{suffix}",
        "first_name": "Postgres",
        "last_name": "Integration",
        "employment_type": "Employee",
        "hire_date": date.today().isoformat(),
    })
    assert employee_response.status_code == 201
    employee = employee_response.json()

    initial_employment = postgres_client.post(
        f"/api/v1/hr/employees/{employee['id']}/employment-records",
        json={
            "position_title": "Analyst",
            "employment_type": "Employee",
            "status": "Active",
            "effective_from": date.today().isoformat(),
            "reason": "Initial appointment",
        },
    )
    assert initial_employment.status_code == 201
    future_date = date.today() + timedelta(days=1)
    scheduled_employment = postgres_client.post(
        f"/api/v1/hr/employees/{employee['id']}/employment-records",
        json={
            "position_title": "Senior Analyst",
            "employment_type": "Employee",
            "status": "Active",
            "effective_from": future_date.isoformat(),
            "reason": "Scheduled promotion",
        },
    )
    assert scheduled_employment.status_code == 201
    assert postgres_client.get(f"/api/v1/hr/employees/{employee['id']}").json()["status"] == "Active"
    history = postgres_client.get(
        f"/api/v1/hr/employees/{employee['id']}/employment-records"
    ).json()
    assert history[0]["effective_from"] == future_date.isoformat()
    assert history[1]["effective_to"] == (future_date - timedelta(days=1)).isoformat()

    compensation_response = postgres_client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"],
        "currency": "INR",
        "pay_basis": "Fixed",
        "gross_amount": "87500.25",
        "frequency": "Monthly",
        "effective_from": date.today().isoformat(),
    })
    assert compensation_response.status_code == 201
    compensation = postgres_client.get(
        f"/api/v1/payroll/compensation?employee_id={employee['id']}"
    )
    assert compensation.status_code == 200
    assert Decimal(str(compensation.json()[0]["gross_amount"])) == Decimal("87500.25")

    period_response = postgres_client.post("/api/v1/payroll/periods", json={
        "period_code": f"PG-{suffix}",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
    })
    assert period_response.status_code == 201
    run_response = postgres_client.post("/api/v1/payroll/runs", json={
        "period_id": period_response.json()["id"],
        "run_code": f"PG-RUN-{suffix}",
        "currency": "INR",
    })
    assert run_response.status_code == 201

    entry_response = postgres_client.post(
        f"/api/v1/payroll/runs/{run_response.json()['id']}/entries",
        json={
            "employee_id": employee["id"],
            "currency": "INR",
            "gross_amount": "87500.25",
            "deduction_total": "12500.25",
            "net_amount": "75000.00",
            "breakdown": {"source": "postgres-integration", "components": ["base", "deductions"]},
        },
    )
    assert entry_response.status_code == 201
    entry = postgres_client.get(
        f"/api/v1/payroll/runs/{run_response.json()['id']}/entries"
    )
    assert entry.status_code == 200
    assert Decimal(str(entry.json()[0]["net_amount"])) == Decimal("75000.00")
    assert entry.json()[0]["breakdown"]["components"] == ["base", "deductions"]

    with SessionLocal() as session:
        actions = set(session.scalars(select(AuditEvent.action).where(
            AuditEvent.organization_id == "postgres-integration-org",
            AuditEvent.entity_id.in_([employee["id"], entry_response.json()["id"]]),
        )).all())
    assert "employee.created" in actions
    assert "payroll_entry.created" in actions
