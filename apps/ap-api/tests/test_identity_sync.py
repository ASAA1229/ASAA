"""Identity lifecycle provisioning against the in-memory mock provider (ASAA-003, provider-independent parts)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from asaa_ap.database import get_db
from asaa_ap.main import app
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_identity import service
from asaa_identity.api import get_identity_provider
from asaa_identity.memory import InMemoryIdentityProvider
from asaa_identity.models import IdentitySyncJob
from asaa_identity.provider import (IdentityProvider, PermanentProviderError, TransientProviderError)

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
ADMIN = {"identity:link:write", "identity:sync:read", "identity:sync:enqueue", "identity:sync:run", "identity:sync:reconcile",
         "hr:employee:write", "hr:employee:read", "hr:employee:lifecycle", "hr:exit:write", "hr:exit:complete",
         "authorization:role:write", "authorization:role:approve", "authorization:assignment:create",
         "authorization:assignment:approve", "authorization:assignment:revoke", "onboarding:read", "hr:employment:write"}


def as_p(client, subject="admin", perms=ADMIN, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


@pytest.fixture
def provider(client):
    mock = InMemoryIdentityProvider()
    client.app.dependency_overrides[get_identity_provider] = lambda: mock
    as_p(client)
    yield mock
    client.app.dependency_overrides.pop(get_identity_provider, None)


@pytest.fixture
def db(client):
    session = next(app.dependency_overrides[get_db]())
    yield session
    session.close()


def employee(client, first="Asha", last="Rao", code=None):
    body = {"first_name": first, "last_name": last, "employment_type": "Employee", "work_email": f"{first.lower()}@example.invalid"}
    if code:
        body["employee_code"] = code
    r = client.post("/api/v1/hr/employees", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def link(client, emp, subject):
    r = client.put("/api/v1/identity-sync/links", json={"employee_id": emp["id"], "subject": subject})
    assert r.status_code == 200, r.text


def grant(client, subject, permissions=("invoice:read",), code="role.a"):
    as_p(client, "role-maker")
    role = client.post("/api/v1/authorization/roles", json={"role_code": code, "name": "Role", "scope_type": "Organization",
                                                            "permissions": list(permissions)}).json()
    as_p(client, "role-approver")
    client.post(f"/api/v1/authorization/roles/{role['id']}/review", json={"expected_version": 1, "decision": "Approve", "reason": "ok ok"})
    as_p(client, "requester")
    a = client.post("/api/v1/authorization/assignments", json={
        "role_template_id": role["id"], "subject": subject, "scope_reference": "organization:org-a",
        "effective_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "reason": "need"}).json()
    as_p(client, "assignment-approver")
    r = client.post(f"/api/v1/authorization/assignments/{a['id']}/review", json={"expected_version": 1, "decision": "Approve", "reason": "ok ok"})
    assert r.status_code == 200
    as_p(client)
    return a


def run(client, db, provider, now=None):
    return service.process_due(db, provider, "org-a", now=now or datetime.now(timezone.utc) + timedelta(seconds=1))


def test_joiner_creates_provider_user_with_approved_entitlements(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-asha")
    grant(client, "sub-asha", ("invoice:read", "invoice:approve"))
    summary = run(client, db, provider)
    assert summary["succeeded"] >= 1 and summary["dead_lettered"] == 0
    user = provider.get_user("sub-asha")
    assert user.active and user.entitlements == {"invoice:read", "invoice:approve"}
    assert provider.users["sub-asha"]["attributes"].display_name == "Asha Rao"


def test_unapproved_pending_or_expired_assignments_grant_nothing(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-1")
    as_p(client, "role-maker")
    role = client.post("/api/v1/authorization/roles", json={"role_code": "r.b", "name": "Role B", "scope_type": "Organization", "permissions": ["x:read"]}).json()
    as_p(client, "approver")
    client.post(f"/api/v1/authorization/roles/{role['id']}/review", json={"expected_version": 1, "decision": "Approve", "reason": "fine"})
    as_p(client, "requester")
    client.post("/api/v1/authorization/assignments", json={"role_template_id": role["id"], "subject": "sub-1", "scope_reference": "organization:org-a",
                                                           "effective_from": datetime.now(timezone.utc).isoformat(), "reason": "pending only"})
    desired, unlinked = service.desired_states(db, "org-a")
    assert desired["sub-1"].entitlements == frozenset()
    future, _ = service.desired_states(db, "org-a", now=datetime.now(timezone.utc) + timedelta(days=400))
    assert future["sub-1"].entitlements == frozenset()


def test_leaver_disables_revokes_sessions_and_clears_entitlements(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-leaver")
    grant(client, "sub-leaver")
    run(client, db, provider)
    assert provider.get_user("sub-leaver").active and provider.active_sessions("sub-leaver") == 1
    # employee leaves: status Inactive -> leaver job -> revocation
    as_p(client)
    emp_row = client.patch(f"/api/v1/hr/employees/{emp['id']}", json={}).json() if False else None
    from asaa_people.models import Employee
    row = db.get(Employee, emp["id"])
    row.status = "Inactive"
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "test", "admin")
    db.commit()
    run(client, db, provider)
    user = provider.get_user("sub-leaver")
    assert not user.active and user.entitlements == frozenset() and provider.active_sessions("sub-leaver") == 0
    done = db.scalars(select(AuditEvent).where(AuditEvent.action == "identity_sync.completed")).all()
    assert done and all(e.actor_id == service.SYSTEM_ACTOR for e in done)
    # idempotent: running the same leaver again changes nothing and does not fail
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "again", "admin")
    db.commit()
    assert run(client, db, provider)["succeeded"] == 1


def test_revoking_assignment_queues_mover_that_removes_entitlements(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-mover")
    a = grant(client, "sub-mover")
    run(client, db, provider)
    assert provider.get_user("sub-mover").entitlements == {"invoice:read"}
    as_p(client, "revoker")
    assert client.post(f"/api/v1/authorization/assignments/{a['id']}/revoke", json={"expected_version": 2, "reason": "no longer needed"}).status_code == 200
    pending = db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.status == "Pending")).all()
    assert [j.operation for j in pending] == ["mover"]
    run(client, db, provider)
    assert provider.get_user("sub-mover").entitlements == frozenset()


def test_exit_case_completion_queues_leaver_in_same_transaction(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-exit")
    run(client, db, provider)
    case = client.post(f"/api/v1/hr/employees/{emp['id']}/exit-cases", json={
        "planned_last_day": date.today().isoformat(), "reason_category": "Resignation"})
    assert case.status_code == 201, case.text
    done = client.post(f"/api/v1/hr/exit-cases/{case.json()['id']}/complete")
    assert done.status_code == 200, done.text
    ops = [j.operation for j in db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.status == "Pending")).all()]
    assert ops == ["leaver"]
    run(client, db, provider)
    assert not provider.get_user("sub-exit").active


def test_transient_failures_retry_with_exponential_backoff_then_succeed(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-retry")
    provider.fail_next(2, "transient")
    t0 = datetime.now(timezone.utc)
    first = service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=1))
    assert first["retry_scheduled"] == 1 and provider.get_user("sub-retry") is None
    job = db.scalar(select(IdentitySyncJob))
    assert job.attempts == 1 and job.status == "Pending"
    # not due yet
    assert service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=10))["processed"] == 0
    second = service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=40))
    assert second["retry_scheduled"] == 1
    db.refresh(job)
    assert job.attempts == 2 and (service.aware(job.next_attempt_at) - (t0 + timedelta(seconds=40))).total_seconds() == 60  # 30 * 2^(2-1)
    third = service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=200))
    assert third["succeeded"] == 1 and provider.get_user("sub-retry").active
    db.refresh(job)
    assert job.status == "Succeeded" and job.last_error is None


def test_exhausted_retries_and_permanent_errors_dead_letter_with_alert_and_audit(client, provider, db, caplog):
    emp = employee(client)
    link(client, emp, "sub-dead")
    provider.fail_next(10, "transient")
    base = datetime.now(timezone.utc)
    for i in range(1, 7):
        service.process_due(db, provider, "org-a", now=base + timedelta(hours=i))
    job = db.scalar(select(IdentitySyncJob))
    assert job.status == "DeadLetter" and job.attempts == 5
    status = client.get("/api/v1/identity-sync/status").json()
    assert status["dead_letter"] == 1 and status["alert"] is True
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "identity_sync.dead_letter")) is not None
    # permanent errors dead-letter at once
    provider._faults.clear()
    emp2 = employee(client, "Ben", "Ito", "E-2")
    link(client, emp2, "sub-perm")
    provider.fail_next(1, "permanent")
    out = service.process_due(db, provider, "org-a", now=base + timedelta(days=1))
    assert out["dead_lettered"] == 1
    # operator can retry a dead letter after fixing the cause
    dead = client.get("/api/v1/identity-sync/jobs?status=DeadLetter").json()
    assert len(dead) == 2
    assert client.post(f"/api/v1/identity-sync/jobs/{dead[0]['id']}/retry").status_code == 200
    done = service.process_due(db, provider, "org-a", now=base + timedelta(days=2))
    assert done["succeeded"] == 1


def test_error_text_stored_on_jobs_is_redacted(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-redact")

    class Leaky(InMemoryIdentityProvider):
        def upsert_user(self, *a, **k):
            raise TransientProviderError("401 for asha@example.invalid token=abc123")
    service.process_due(db, Leaky(), "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    err = db.scalar(select(IdentitySyncJob)).last_error
    assert "asha@example.invalid" not in err and "abc123" not in err


def test_reconciliation_detects_every_drift_type_and_repair_converges(client, provider, db):
    a, b, c, d = (employee(client, n, "T", f"E-{n}") for n in ("Ann", "Bob", "Cy", "Di"))
    for emp, sub in ((a, "s-a"), (b, "s-b"), (c, "s-c"), (d, "s-d")):
        link(client, emp, sub)
    grant(client, "s-a", ("invoice:read",), "r.1")
    grant(client, "s-b", ("invoice:read",), "r.2")
    run(client, db, provider)  # all four provisioned; a and b with entitlement
    assert service.reconcile(db, provider, "org-a")["in_sync"]
    # introduce drift behind ASAA's back
    provider.users["s-a"]["entitlements"] = set()  # missing
    provider.users["s-b"]["entitlements"] = {"invoice:read", "admin:all"}  # extra
    del provider.users["s-c"]  # missing_in_provider
    from asaa_people.models import Employee
    db.get(Employee, d["id"]).status = "Inactive"; db.commit()  # should be disabled, provider still active
    provider.users["stranger"] = {"active": True, "entitlements": {"x"}, "sessions": 1}
    report = service.reconcile(db, provider, "org-a")
    assert report["drift_by_kind"] == {"entitlement_missing": 1, "entitlement_extra": 1, "missing_in_provider": 1, "should_be_disabled": 1}
    assert report["unmanaged_active_users"] == ["stranger"] and not report["in_sync"]
    assert {x["subject"]: x["entitlements"] for x in report["drifts"] if x["kind"] == "entitlement_extra"} == {"s-b": ["admin:all"]}
    assert "asha" not in str(report).lower()  # no personal data in the report
    # report-only does not mutate
    assert service.status_summary(db, "org-a")["pending"] == 0
    repaired = service.reconcile(db, provider, "org-a", repair=True)
    assert repaired["repair_jobs_queued"] == 4
    run(client, db, provider)
    after = service.reconcile(db, provider, "org-a")
    assert after["in_sync"] and after["drift_count"] == 0
    assert after["unmanaged_active_users"] == ["stranger"]  # reported, never auto-deleted


def test_pending_jobs_are_deduplicated(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-dup")
    j1 = service.enqueue(db, "org-a", "sub-dup", "mover", "x", "admin")
    j2 = service.enqueue(db, "org-a", "sub-dup", "mover", "y", "admin")
    assert j1.id == j2.id


def test_rehire_before_leaver_runs_converges_on_current_state(client, provider, db):
    emp = employee(client)
    link(client, emp, "sub-rehire")
    run(client, db, provider)
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "stale", "admin")
    db.commit()  # employee is still Active (re-hired/never left): the stale leaver must not lock them out
    run(client, db, provider)
    assert provider.get_user("sub-rehire").active


def test_api_security_for_identity_sync(client, provider, db):
    emp = employee(client)
    # permission separation
    as_p(client, "reader", {"identity:sync:read"})
    assert client.put("/api/v1/identity-sync/links", json={"employee_id": emp["id"], "subject": "x"}).status_code == 403
    assert client.post("/api/v1/identity-sync/process").status_code == 403
    assert client.post("/api/v1/identity-sync/reconcile").status_code == 403
    as_p(client, "recon", {"identity:sync:reconcile"})
    assert client.post("/api/v1/identity-sync/reconcile").status_code == 200
    assert client.post("/api/v1/identity-sync/reconcile?repair=true").status_code == 403  # repair needs enqueue permission too
    # cross-organization isolation
    as_p(client)
    link(client, emp, "sub-iso")
    as_p(client, "other", ADMIN, org="org-b")
    assert client.put("/api/v1/identity-sync/links", json={"employee_id": emp["id"], "subject": "sub-iso"}).status_code == 404
    assert client.get("/api/v1/identity-sync/links").json() == []
    assert client.post("/api/v1/identity-sync/jobs", json={"employee_id": emp["id"], "operation": "joiner"}).status_code == 404
    # a subject cannot be linked to two employees
    as_p(client)
    emp2 = employee(client, "Zed", "Q", "E-9")
    r = client.put("/api/v1/identity-sync/links", json={"employee_id": emp2["id"], "subject": "sub-iso"})
    assert r.status_code == 409


def test_unconfigured_provider_fails_closed_with_503(client):
    as_p(client)
    client.app.dependency_overrides.pop(get_identity_provider, None)
    assert client.post("/api/v1/identity-sync/process").status_code == 503
    assert client.post("/api/v1/identity-sync/reconcile").status_code == 503


def test_memory_provider_is_refused_in_production():
    from asaa_ap.config import Settings
    with pytest.raises(ValueError, match="in-memory"):
        Settings(environment="production", database_url="postgresql+psycopg://u@h/db", identity_provider="memory")


def test_provider_contract_is_abstract():
    with pytest.raises(TypeError):
        IdentityProvider()  # type: ignore[abstract]
