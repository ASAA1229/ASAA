"""Template validation/rendering, preferences, outbox processing with retry and dead-letter."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_ap.models import AuditEvent
from asaa_ap.observability import redact
from asaa_identity.provider import PermanentProviderError, ProviderError, TransientProviderError
from asaa_notifications.models import NotificationMessage, NotificationPreference, NotificationTemplate
from asaa_notifications.provider import NotificationProvider

log = logging.getLogger("asaa.notifications")
SYSTEM_ACTOR = "system:notifications"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
VARIABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# Sensitive-content minimization: notifications must not carry these kinds of data, so such variables cannot be declared.
FORBIDDEN_VARIABLE_PARTS = ("salary", "gross", "net_", "deduction", "bank", "account", "password", "secret", "token", "ssn", "tax",
                            "dob", "birth", "address", "phone", "email", "aadhaar", "pan", "compensation", "payroll", "breakdown")
CHANNELS = {"email", "sms", "chat", "in_app"}
MAX_VALUE_LENGTH = 200


class TemplateError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def validate_template(subject_template: str, body_template: str, allowed_variables: list[str]) -> None:
    for name in allowed_variables:
        if not VARIABLE_NAME.match(name):
            raise TemplateError(f"invalid variable name {name!r}")
        if any(part in name for part in FORBIDDEN_VARIABLE_PARTS):
            raise TemplateError(f"variable {name!r} could carry sensitive data and is not permitted in notifications")
    used = set(PLACEHOLDER.findall(subject_template)) | set(PLACEHOLDER.findall(body_template))
    unknown = used - set(allowed_variables)
    if unknown:
        raise TemplateError("template uses undeclared variables: " + ", ".join(sorted(unknown)))
    stray = re.sub(PLACEHOLDER, "", subject_template + body_template)
    if "{{" in stray or "}}" in stray:
        raise TemplateError("malformed placeholder")


def _clean(value) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    if len(text) > MAX_VALUE_LENGTH:
        raise TemplateError("variable value too long")
    return text


def render(template: NotificationTemplate, variables: dict) -> tuple[str, str]:
    allowed = set(template.allowed_variables)
    extra = set(variables) - allowed
    if extra:
        raise TemplateError("undeclared variables supplied: " + ", ".join(sorted(extra)))
    missing = allowed - set(variables)
    if missing:
        raise TemplateError("missing variables: " + ", ".join(sorted(missing)))
    sub = lambda text: PLACEHOLDER.sub(lambda m: _clean(variables[m.group(1)]), text)  # noqa: E731
    return sub(template.subject_template), sub(template.body_template)


def is_enabled(db: Session, organization_id: str, subject: str, channel: str) -> bool:
    pref = db.scalar(select(NotificationPreference).where(
        NotificationPreference.organization_id == organization_id, NotificationPreference.subject == subject,
        NotificationPreference.channel == channel))
    return True if pref is None else pref.enabled


def enqueue(db: Session, organization_id: str, recipient_subject: str, template_code: str, variables: dict,
            channel: str = "email", idempotency_key: str | None = None, correlation_id: str | None = None,
            now: datetime | None = None) -> NotificationMessage | None:
    """Queue a notification in the caller's transaction (caller commits). Returns None when no active template exists
    (domain code can call this unconditionally). Idempotent per idempotency_key."""
    template = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.organization_id == organization_id, NotificationTemplate.code == template_code,
        NotificationTemplate.channel == channel, NotificationTemplate.active.is_(True)))
    if template is None:
        return None
    key = idempotency_key or f"{template_code}:{recipient_subject}:{(now or utcnow()).isoformat()}"
    existing = db.scalar(select(NotificationMessage).where(
        NotificationMessage.organization_id == organization_id, NotificationMessage.idempotency_key == key))
    if existing:
        return existing
    subject_text, body_text = render(template, variables)
    suppressed = not is_enabled(db, organization_id, recipient_subject, channel)
    message = NotificationMessage(
        organization_id=organization_id, recipient_subject=recipient_subject, template_code=template_code, channel=channel,
        subject_text=subject_text, body_text=body_text, idempotency_key=key, correlation_id=correlation_id,
        status="Suppressed" if suppressed else "Pending", next_attempt_at=now or utcnow())
    db.add(message)
    db.flush()
    return message


def backoff_seconds(attempts: int, base: int = 60, cap: int = 3600) -> int:
    return min(cap, base * (2 ** max(0, attempts - 1)))


def _audit(db, message, action, outcome, details):
    db.add(AuditEvent(organization_id=message.organization_id, actor_id=SYSTEM_ACTOR, action=action, entity_type="notification_message",
                      entity_id=message.id, outcome=outcome, details=details, correlation_id=message.correlation_id))


def process_due(db: Session, provider: NotificationProvider, organization_id: str | None = None, now: datetime | None = None,
                limit: int = 100, backoff_base: int = 60, backoff_cap: int = 3600) -> dict:
    now = now or utcnow()
    stmt = select(NotificationMessage).where(NotificationMessage.status == "Pending", NotificationMessage.next_attempt_at <= now)
    if organization_id:
        stmt = stmt.where(NotificationMessage.organization_id == organization_id)
    summary = {"processed": 0, "sent": 0, "retry_scheduled": 0, "dead_lettered": 0}
    for message in db.scalars(stmt.order_by(NotificationMessage.next_attempt_at).limit(limit)).all():
        summary["processed"] += 1
        message.attempts += 1
        # Re-check the preference at send time: an opt-out after queueing must still be honoured.
        if not is_enabled(db, message.organization_id, message.recipient_subject, message.channel):
            message.status = "Suppressed"
            db.commit()
            continue
        try:
            provider.send(message.channel, message.recipient_subject, message.subject_text, message.body_text, message.id)
        except TransientProviderError as exc:
            message.last_error = f"transient: {redact(str(exc))}"[:300]
            if message.attempts >= message.max_attempts:
                _dead_letter(db, message, "retries_exhausted")
                summary["dead_lettered"] += 1
            else:
                message.next_attempt_at = now + timedelta(seconds=backoff_seconds(message.attempts, backoff_base, backoff_cap))
                summary["retry_scheduled"] += 1
        except (PermanentProviderError, ProviderError) as exc:
            message.last_error = f"permanent: {redact(str(exc))}"[:300]
            _dead_letter(db, message, "permanent_error")
            summary["dead_lettered"] += 1
        else:
            message.status, message.sent_at, message.last_error = "Sent", now, None
            _audit(db, message, "notification.sent", "success", {"template": message.template_code, "channel": message.channel, "attempts": message.attempts})
            summary["sent"] += 1
        db.commit()
    return summary


def _dead_letter(db, message, cause):
    message.status = "DeadLetter"
    _audit(db, message, "notification.dead_letter", "failure", {"template": message.template_code, "attempts": message.attempts, "cause": cause})
    log.error("notification_dead_letter", extra={"message_id": message.id, "template": message.template_code, "attempts": message.attempts, "cause": cause})


def retry_dead_letter(db: Session, organization_id: str, message_id: str, now: datetime | None = None):
    message = db.scalar(select(NotificationMessage).where(NotificationMessage.id == message_id, NotificationMessage.organization_id == organization_id))
    if message is None or message.status != "DeadLetter":
        return None
    message.status, message.attempts, message.next_attempt_at = "Pending", 0, now or utcnow()
    db.commit()
    return message


def status_summary(db: Session, organization_id: str, now: datetime | None = None, stale_after_seconds: int = 900) -> dict:
    now = now or utcnow()
    counts = dict(db.execute(select(NotificationMessage.status, func.count()).where(
        NotificationMessage.organization_id == organization_id).group_by(NotificationMessage.status)).all())
    pending = db.scalars(select(NotificationMessage).where(
        NotificationMessage.organization_id == organization_id, NotificationMessage.status == "Pending")).all()
    stale = [m for m in pending if (now - aware(m.created_at)).total_seconds() > stale_after_seconds]
    return {"pending": counts.get("Pending", 0), "sent": counts.get("Sent", 0), "dead_letter": counts.get("DeadLetter", 0),
            "suppressed": counts.get("Suppressed", 0), "stale_pending": len(stale),
            "alert": bool(counts.get("DeadLetter", 0) or stale)}
