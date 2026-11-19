"""Notification outbox: templates, minimization, preferences, retry/dead-letter, isolation (ASAA-P1-10 / P1-15, provider independent)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from asaa_ap.database import get_db
from asaa_ap.main import app
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_notifications import service
from asaa_notifications.api import get_notification_provider
from asaa_notifications.models import NotificationMessage
from asaa_notifications.provider import InMemoryNotificationProvider, NotificationProvider

ADMIN = {"notification:template:write", "notification:template:read", "notification:send", "notification:outbox:read",
         "notification:process", "hr:employee:write", "hr:employee:read", "hr:leave:request", "hr:leave:review", "hr:leave:read"}


def as_p(client, subject="admin", perms=ADMIN, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


@pytest.fixture
def provider(client):
    mock = InMemoryNotificationProvider()
    client.app.dependency_overrides[get_notification_provider] = lambda: mock
    as_p(client)
    yield mock
    client.app.dependency_overrides.pop(get_notification_provider, None)


@pytest.fixture
def db(client):
    session = next(app.dependency_overrides[get_db]())
    yield session
    session.close()


def template(client, code="approval.requested", variables=("item",), subject="Action needed: {{item}}", body="Please review {{item}}.", channel="email"):
    r = client.post("/api/v1/notifications/templates", json={"code": code, "channel": channel, "subject_template": subject,
                                                             "body_template": body, "allowed_variables": list(variables)})
    return r


def send(client, **kw):
    body = {"recipient_subject": "alice", "template_code": "approval.requested", "variables": {"item": "Invoice 42"}, **kw}
    return client.post("/api/v1/notifications/send", json=body)


def due(db, provider, offset=1, **kw):
    return service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=offset), **kw)


def test_template_render_send_and_audit(client, provider, db):
    assert template(client).status_code == 201
    queued = send(client, idempotency_key="k1")
    assert queued.status_code == 202 and queued.json()["status"] == "Pending"
    assert queued.json()["subject"] == "Action needed: Invoice 42"
    assert due(db, provider)["sent"] == 1
    assert provider.sent[0]["to"] == "alice" and provider.sent[0]["body"] == "Please review Invoice 42."
    assert client.get("/api/v1/notifications/messages?status=Sent").json()[0]["sent_at"]
    actions = {e.action for e in db.scalars(select(AuditEvent)).all()}
    assert {"notification_template.created", "notification.queued", "notification.sent"} <= actions


def test_idempotency_prevents_duplicate_sends(client, provider, db):
    template(client)
    first, second = send(client, idempotency_key="same").json(), send(client, idempotency_key="same").json()
    assert first["id"] == second["id"]
    due(db, provider)
    due(db, provider, offset=5)
    assert len(provider.sent) == 1


def test_sensitive_content_is_refused_in_templates(client, provider):
    for bad in ("salary", "gross_amount", "bank_account", "password_hint", "work_email", "phone_number", "tax_id", "net_pay"):
        r = template(client, code=f"bad.{bad[:6]}", variables=(bad,), subject="x {{" + bad + "}}", body="y")
        assert r.status_code == 422 and "sensitive" in r.json()["detail"]["message"], bad
    assert template(client, code="undeclared", variables=(), subject="Hi {{name}}", body="b").status_code == 422
    assert template(client, code="malformed", variables=("a",), subject="Hi {{a", body="b").status_code == 422
    assert template(client, code="BadCode!", variables=()).status_code == 422


def test_variable_validation_at_send_time(client, provider):
    template(client)
    assert send(client, variables={}).status_code == 422  # missing
    assert send(client, variables={"item": "x", "salary": "100"}).status_code == 422  # undeclared extra
    assert send(client, variables={"item": "x" * 500}).status_code == 422  # too long
    assert send(client, template_code="missing.template").status_code == 404
    ok = send(client, variables={"item": "line1\nline2\x00"}).json()
    assert "\n" not in ok["subject"] and "\x00" not in ok["subject"]


def test_preferences_suppress_delivery_even_when_changed_after_queueing(client, provider, db):
    template(client)
    queued = send(client, idempotency_key="before-optout").json()
    as_p(client, "alice", set())  # alice, no permissions, controls only her own preference
    assert client.put("/api/v1/notifications/preferences/me", json={"channel": "email", "enabled": False}).json()["enabled"] is False
    assert client.get("/api/v1/notifications/preferences/me").json()["email"] is False
    as_p(client)
    assert due(db, provider)["sent"] == 0 and provider.sent == []
    assert client.get("/api/v1/notifications/messages?status=Suppressed").json()[0]["id"] == queued["id"]
    # a message queued after the opt-out is recorded as Suppressed immediately and never sent
    assert send(client, idempotency_key="after-optout").json()["status"] == "Suppressed"
    assert service.status_summary(db, "org-a")["suppressed"] == 2
    # preferences are per person: bob is unaffected
    assert send(client, recipient_subject="bob", idempotency_key="bob").json()["status"] == "Pending"


def test_preference_endpoint_only_touches_the_callers_own_record(client, provider, db):
    as_p(client, "mallory", set())
    client.put("/api/v1/notifications/preferences/me", json={"channel": "sms", "enabled": False})
    assert client.put("/api/v1/notifications/preferences/me", json={"channel": "sms", "enabled": False, "subject": "alice"}).status_code == 422
    as_p(client, "alice", set())
    assert client.get("/api/v1/notifications/preferences/me").json()["sms"] is True
    as_p(client, "mallory", set(), org="org-b")
    assert client.get("/api/v1/notifications/preferences/me").json()["sms"] is True  # other organization


def test_transient_failures_back_off_then_succeed_and_exhaustion_dead_letters(client, provider, db):
    template(client)
    send(client, idempotency_key="retry")
    provider.fail_next(2)
    t0 = datetime.now(timezone.utc)
    assert service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=1))["retry_scheduled"] == 1
    msg = db.scalar(select(NotificationMessage))
    assert msg.attempts == 1 and msg.status == "Pending"
    assert service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=10))["processed"] == 0  # backoff not elapsed
    assert service.process_due(db, provider, "org-a", now=t0 + timedelta(seconds=90))["retry_scheduled"] == 1
    assert (service.aware(msg.next_attempt_at) - (t0 + timedelta(seconds=90))).total_seconds() == 120  # 60 * 2
    assert service.process_due(db, provider, "org-a", now=t0 + timedelta(hours=1))["sent"] == 1
    # exhaustion
    send(client, idempotency_key="doomed")
    provider.fail_next(20)
    for i in range(1, 7):
        service.process_due(db, provider, "org-a", now=t0 + timedelta(days=1, hours=i))
    status = client.get("/api/v1/notifications/status").json()
    assert status["dead_letter"] == 1 and status["alert"] is True
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "notification.dead_letter")) is not None


def test_permanent_error_dead_letters_immediately_and_operator_can_retry(client, provider, db):
    template(client)
    send(client, idempotency_key="perm")
    provider.fail_next(1, "permanent")
    assert due(db, provider)["dead_lettered"] == 1
    dead = client.get("/api/v1/notifications/messages?status=DeadLetter").json()
    assert len(dead) == 1
    assert client.post(f"/api/v1/notifications/messages/{dead[0]['id']}/retry").status_code == 200
    assert due(db, provider, offset=5)["sent"] == 1


def test_error_text_on_messages_is_redacted(client, provider, db):
    from asaa_identity.provider import TransientProviderError
    template(client)
    send(client, idempotency_key="leak")

    class Leaky(NotificationProvider):
        def send(self, *a, **k):
            raise TransientProviderError("rejected for asha@example.invalid token=abc123")
    service.process_due(db, Leaky(), "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    err = db.scalar(select(NotificationMessage)).last_error
    assert "asha@example.invalid" not in err and "abc123" not in err


def test_permissions_and_organization_isolation(client, provider, db):
    template(client)
    send(client, idempotency_key="iso")
    as_p(client, "reader", {"notification:outbox:read"})
    assert client.post("/api/v1/notifications/send", json={"recipient_subject": "a", "template_code": "x.y", "variables": {}}).status_code == 403
    assert client.post("/api/v1/notifications/process").status_code == 403
    assert client.get("/api/v1/notifications/templates").status_code == 403
    assert len(client.get("/api/v1/notifications/messages").json()) == 1
    as_p(client, "other", ADMIN, org="org-b")
    assert client.get("/api/v1/notifications/messages").json() == []
    assert client.get("/api/v1/notifications/templates").json() == []
    assert send(client).status_code == 404  # org-b has no template
    as_p(client)
    assert template(client).status_code == 409  # duplicate template code+channel in the same org


def test_unconfigured_provider_fails_closed_and_memory_is_refused_in_production(client):
    as_p(client)
    client.app.dependency_overrides.pop(get_notification_provider, None)
    assert client.post("/api/v1/notifications/process").status_code == 503
    from asaa_ap.config import Settings
    with pytest.raises(ValueError, match="in-memory notification"):
        Settings(environment="production", database_url="postgresql+psycopg://u@h/db", notification_provider="memory")


def test_leave_review_queues_a_notification_for_the_requester(client, provider, db):
    from datetime import date
    assert template(client, code="leave.reviewed", variables=("decision",), subject="Leave request {{decision}}",
                    body="Your leave request was {{decision}}.").status_code == 201
    emp = client.post("/api/v1/hr/employees", json={"first_name": "Lee", "last_name": "Ve", "employment_type": "Employee"}).json()
    as_p(client, "requester")
    leave = client.post(f"/api/v1/hr/employees/{emp['id']}/leave-requests", json={
        "leave_category": "Annual", "start_date": (date.today() + timedelta(days=30)).isoformat(),
        "end_date": (date.today() + timedelta(days=31)).isoformat(), "reason": "Family event"})
    assert leave.status_code == 201, leave.text
    as_p(client, "manager")
    reviewed = client.post(f"/api/v1/hr/leave-requests/{leave.json()['id']}/review", json={"decision": "Approved", "review_note": "ok"})
    assert reviewed.status_code == 200, reviewed.text
    queued = db.scalars(select(NotificationMessage).where(NotificationMessage.template_code == "leave.reviewed")).all()
    assert [(m.recipient_subject, m.body_text) for m in queued] == [("requester", "Your leave request was Approved.")]
    assert due(db, provider)["sent"] == 1 and provider.sent[0]["to"] == "requester"
    # without a template the hook is a harmless no-op
    other = client.post(f"/api/v1/hr/employees/{emp['id']}/leave-requests", json={
        "leave_category": "Annual", "start_date": (date.today() + timedelta(days=60)).isoformat(),
        "end_date": (date.today() + timedelta(days=61)).isoformat(), "reason": "Later"})
    assert other.status_code == 201
