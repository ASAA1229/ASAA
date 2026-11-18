"""Critical ecosystem events raise notifications through the existing outbox: recipients, idempotency, isolation."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from tests.integration_support import (URL, as_producer, install_settings, integration_settings, jarvis_envelope)  # noqa: F401
from asaa_governance.authorization import AuthorizationAssignment, AuthorizationRoleTemplate
from asaa_integration import alerts
from asaa_integration.models import IntegrationEvent
from asaa_notifications import service as notification_service
from asaa_notifications.models import NotificationMessage, NotificationPreference, NotificationTemplate

NOW = datetime.now(timezone.utc)


def db_of(client):
    return next(client.app.dependency_overrides[get_db]())


def as_writer(client, org="org-a"):
    as_producer(client, "jarvis-events", org)


def envelope(severity="critical", **over):
    return jarvis_envelope(severity=severity, **over)


def grant(session, subject, permissions, org="org-a", status="Approved", role_status="Active", start=None, end=None):
    role = AuthorizationRoleTemplate(organization_id=org, role_code=f"r{uuid.uuid4().hex[:8]}", name="Role", scope_type="Organization",
                                     permissions=permissions, status=role_status, created_by="admin")
    session.add(role)
    session.flush()
    session.add(AuthorizationAssignment(organization_id=org, role_template_id=role.id, subject=subject, scope_reference="org",
                                        effective_from=start or NOW - timedelta(days=1), effective_to=end, reason="test", status=status,
                                        created_by="admin"))
    session.commit()


def messages(session, org="org-a"):
    return session.scalars(select(NotificationMessage).where(NotificationMessage.organization_id == org)
                           .order_by(NotificationMessage.recipient_subject)).all()


@pytest.fixture
def writer(client):
    as_writer(client)
    return client


def test_critical_event_notifies_role_holders_with_event_or_ops_permission(writer):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    grant(s, "bob", ["ops:ecosystem:read", "audit:read"])
    grant(s, "carol", ["supplier:read"])
    body = envelope()
    assert writer.post(URL, json=body, headers={"X-Correlation-ID": "corr-alert-1234"}).status_code == 201
    rows = messages(s)
    assert [m.recipient_subject for m in rows] == ["alice", "bob"]
    for m in rows:
        assert m.template_code == "integration.event.critical" and m.status == "Pending" and m.channel == "email"
        assert "jarvis.security.audit-integrity-failed" in m.subject_text and "JARVIS" in m.subject_text
        assert "audit/chain-7" not in m.body_text + m.subject_text  # the producer-supplied subject is never interpolated
        assert "brokenAt" not in m.body_text and "41" not in m.body_text  # payload is never copied
        assert m.idempotency_key == f"integration.critical:jarvis:jarvis.security.audit-integrity-failed:{body['id']}:{m.recipient_subject}"
        assert m.correlation_id == "corr-alert-1234"
    audit = s.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received")).one()
    assert audit.details["notifications_queued"] == 2


def test_only_critical_events_notify(writer):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    for severity in ("info", "warning"):
        assert writer.post(URL, json=envelope(severity=severity)).status_code == 201
    assert messages(s) == []
    assert s.scalar(select(NotificationTemplate.id)) is None


def test_duplicate_delivery_and_reprocessing_do_not_queue_twice(writer):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    body = envelope()
    assert writer.post(URL, json=body).status_code == 201
    assert writer.post(URL, json=body).json()["status"] == "duplicate"
    assert len(messages(s)) == 1
    event = s.get(IntegrationEvent, (body["id"], "org-a"))
    assert alerts.notify_critical(s, event) == 0  # idempotent per event and recipient (and inside the dedupe window)
    s.commit()
    assert len(messages(s)) == 1


def test_expired_pending_revoked_and_inactive_role_grants_are_ignored(writer):
    s = db_of(writer)
    grant(s, "expired", ["integration:event:read"], end=NOW - timedelta(hours=1))
    grant(s, "future", ["integration:event:read"], start=NOW + timedelta(days=1))
    grant(s, "pending", ["integration:event:read"], status="Pending Approval")
    grant(s, "revoked", ["integration:event:read"], status="Revoked")
    grant(s, "proposed-role", ["integration:event:read"], role_status="Proposed")
    grant(s, "valid", ["integration:event:read"], end=NOW + timedelta(days=1))
    assert writer.post(URL, json=envelope()).status_code == 201
    assert [m.recipient_subject for m in messages(s)] == ["valid"]


def test_other_orgs_are_never_notified(writer):
    s = db_of(writer)
    grant(s, "other-org-admin", ["integration:event:read"], org="org-b")
    grant(s, "alice", ["integration:event:read"])
    assert writer.post(URL, json=envelope()).status_code == 201
    assert [m.recipient_subject for m in messages(s)] == ["alice"]
    assert messages(s, "org-b") == []


def test_configured_recipients_cover_token_only_access_and_are_deduplicated(writer, monkeypatch):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    install_settings(monkeypatch, integration_critical_recipients=["alice", "oncall"])
    assert writer.post(URL, json=envelope()).status_code == 201
    assert [m.recipient_subject for m in messages(s)] == ["alice", "oncall"]


def test_configured_channel_is_used(writer, monkeypatch):
    s = db_of(writer)
    install_settings(monkeypatch, integration_critical_recipients=["oncall"], integration_critical_channel="in_app")
    assert writer.post(URL, json=envelope()).status_code == 201
    assert [(m.recipient_subject, m.channel) for m in messages(s)] == [("oncall", "in_app")]


def test_no_recipients_still_accepts_the_event(writer):
    s = db_of(writer)
    assert writer.post(URL, json=envelope()).status_code == 201
    assert messages(s) == [] and s.scalars(select(IntegrationEvent)).first() is not None


def test_recipient_notification_preference_is_respected(writer):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    s.add(NotificationPreference(organization_id="org-a", subject="alice", channel="email", enabled=False))
    s.commit()
    assert writer.post(URL, json=envelope()).status_code == 201
    assert [(m.recipient_subject, m.status) for m in messages(s)] == [("alice", "Suppressed")]


def test_a_notification_failure_never_loses_the_event(writer, monkeypatch):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])

    def boom(*args, **kwargs):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(notification_service, "enqueue", boom)
    body = envelope()
    response = writer.post(URL, json=body)
    assert response.status_code == 201
    assert s.get(IntegrationEvent, (body["id"], "org-a")) is not None and messages(s) == []
    audit = s.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received")).one()
    assert audit.details["notifications_queued"] == 0


def test_queued_messages_are_deliverable_by_the_existing_outbox_processor(writer):
    from asaa_notifications.provider import InMemoryNotificationProvider
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    assert writer.post(URL, json=envelope()).status_code == 201
    provider = InMemoryNotificationProvider()
    notification_service.process_due(s, provider, "org-a")
    assert [m.status for m in messages(s)] == ["Sent"] and len(provider.sent) == 1


def test_repeated_critical_events_of_one_kind_alert_once_within_the_window(writer):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    assert writer.post(URL, json=envelope()).status_code == 201
    second = writer.post(URL, json=envelope())
    assert second.status_code == 201
    assert [m.recipient_subject for m in messages(s)] == ["alice"]
    audits = s.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received").order_by(AuditEvent.created_at)).all()
    assert [a.details["notifications_queued"] for a in audits] == [1, 0]
    # A different type is a different alert stream.
    assert writer.post(URL, json=envelope(type="jarvis.security.policy-violated")).status_code == 201
    assert len(messages(s)) == 2


def test_dedupe_window_expires_and_can_be_disabled(writer, monkeypatch):
    s = db_of(writer)
    grant(s, "alice", ["integration:event:read"])
    assert writer.post(URL, json=envelope()).status_code == 201
    for message in messages(s):  # pretend the first alert was sent an hour ago
        message.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    s.commit()
    assert writer.post(URL, json=envelope()).status_code == 201
    assert len(messages(s)) == 2
    install_settings(monkeypatch, integration_critical_dedupe_minutes=0)
    assert writer.post(URL, json=envelope()).status_code == 201
    assert len(messages(s)) == 3


def test_a_legacy_template_that_interpolated_the_subject_is_replaced(writer):
    s = db_of(writer)
    s.add(NotificationTemplate(organization_id="org-a", code="integration.event.critical", channel="email", subject_template="x {{project}}",
                               body_template="Subject: {{subject}} {{source}} {{event_type}} {{project}}",
                               allowed_variables=["source", "event_type", "project", "subject"], active=True, created_by="system:integration"))
    grant(s, "alice", ["integration:event:read"])
    s.commit()
    assert writer.post(URL, json=envelope(subject="evil/subject")).status_code == 201
    template = s.scalars(select(NotificationTemplate)).one()
    assert "subject" not in template.allowed_variables and template.version == 2
    assert "evil/subject" not in messages(s)[0].body_text
