"""Raise notifications through the existing outbox for critical ecosystem events (for example jarvis.security.audit-integrity-failed).

Recipients are the subjects holding an approved, in-window role assignment whose active role grants one of ALERT_PERMISSIONS
(the same grants the identity-sync service uses), plus the optional ASAA_AP_INTEGRATION_CRITICAL_RECIPIENTS list. JWT permissions
are not stored server-side, so a subject whose access only comes from a token claim must be listed explicitly.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.config import get_settings
from asaa_governance.authorization import AuthorizationAssignment, AuthorizationRoleTemplate
from asaa_integration.models import IntegrationEvent
from asaa_notifications import service
from asaa_notifications.models import NotificationTemplate

log = logging.getLogger("asaa.integration")
ALERT_PERMISSIONS = frozenset({"integration:event:read", "ops:ecosystem:read"})
TEMPLATE_CODE = "integration.event.critical"
TEMPLATE_VARIABLES = ["source", "event_type", "project", "subject"]
SYSTEM_ACTOR = "system:integration"


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def resolve_recipients(db: Session, organization_id: str, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    subjects: set[str] = set(get_settings().integration_critical_recipients)
    rows = db.execute(select(AuthorizationAssignment, AuthorizationRoleTemplate).join(
        AuthorizationRoleTemplate, AuthorizationRoleTemplate.id == AuthorizationAssignment.role_template_id).where(
        AuthorizationAssignment.organization_id == organization_id, AuthorizationAssignment.status == "Approved",
        AuthorizationRoleTemplate.organization_id == organization_id, AuthorizationRoleTemplate.status == "Active")).all()
    for assignment, role in rows:
        start, end = _aware(assignment.effective_from), _aware(assignment.effective_to)
        if start <= now and (end is None or end > now) and ALERT_PERMISSIONS & set(role.permissions):
            subjects.add(assignment.subject)
    return sorted(subjects)


def ensure_template(db: Session, organization_id: str, channel: str) -> None:
    exists = db.scalar(select(NotificationTemplate.id).where(
        NotificationTemplate.organization_id == organization_id, NotificationTemplate.code == TEMPLATE_CODE,
        NotificationTemplate.channel == channel))
    if exists:
        return
    db.add(NotificationTemplate(
        organization_id=organization_id, code=TEMPLATE_CODE, channel=channel,
        subject_template="Critical {{project}} event: {{event_type}}",
        body_template="A critical event of type {{event_type}} was reported by {{source}} for project {{project}} (subject: {{subject}}). "
                      "Open Integrations & connectors in ASAA to review it. No event payload is included in this message.",
        allowed_variables=list(TEMPLATE_VARIABLES), active=True, created_by=SYSTEM_ACTOR))
    db.flush()


def notify_critical(db: Session, event: IntegrationEvent, correlation_id: str | None = None) -> int:
    """Queue one notification per recipient (idempotent per event id and recipient) in the caller's transaction.
    Never raises: a notification problem must not lose the event."""
    if event.severity != "critical":
        return 0
    try:
        with db.begin_nested():
            channel = get_settings().integration_critical_channel
            recipients = resolve_recipients(db, event.organization_id)
            if not recipients:
                log.warning("critical_event_without_recipients", extra={"event_id": event.id, "event_type": event.type})
                return 0
            ensure_template(db, event.organization_id, channel)
            variables = {"source": event.source, "event_type": event.type, "project": event.project, "subject": event.subject or "-"}
            queued = 0
            for recipient in recipients:
                message = service.enqueue(db, event.organization_id, recipient, TEMPLATE_CODE, variables, channel=channel,
                                          idempotency_key=f"integration.critical:{event.id}:{recipient}", correlation_id=correlation_id)
                queued += 1 if message is not None else 0
            return queued
    except Exception as exc:  # noqa: BLE001 - see docstring
        log.error("critical_event_notification_failed", extra={"event_id": event.id, "error_type": type(exc).__name__})
        return 0
