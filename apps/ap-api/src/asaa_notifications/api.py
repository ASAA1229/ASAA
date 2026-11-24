from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.config import get_settings
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal, require_permission
from asaa_notifications import service
from asaa_notifications.models import NotificationMessage, NotificationPreference, NotificationTemplate
from asaa_notifications.provider import NotificationProvider, resolve_notification_provider

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])
Db = Annotated[Session, Depends(get_db)]


def get_notification_provider() -> NotificationProvider:
    provider = resolve_notification_provider(get_settings().notification_provider)
    if provider is None:
        raise HTTPException(status_code=503, detail="No notification provider is configured")
    return provider


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateCreate(Strict):
    code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    channel: str = Field(pattern="^(email|sms|chat|in_app)$")
    subject_template: str = Field(min_length=1, max_length=300)
    body_template: str = Field(min_length=1, max_length=4000)
    allowed_variables: list[str] = Field(default_factory=list, max_length=20)


class SendRequest(Strict):
    recipient_subject: str = Field(min_length=1, max_length=128)
    template_code: str = Field(min_length=2, max_length=80)
    channel: str = Field(default="email", pattern="^(email|sms|chat|in_app)$")
    variables: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class PreferenceWrite(Strict):
    channel: str = Field(pattern="^(email|sms|chat|in_app)$")
    enabled: bool


def dump(m: NotificationMessage) -> dict:
    return {"id": m.id, "recipient_subject": m.recipient_subject, "template_code": m.template_code, "channel": m.channel,
            "subject": m.subject_text, "status": m.status, "attempts": m.attempts, "max_attempts": m.max_attempts,
            "next_attempt_at": m.next_attempt_at, "last_error": m.last_error, "created_at": m.created_at, "sent_at": m.sent_at}


def _audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, correlation_id=correlation_id))


@router.post("/templates", status_code=201)
def create_template(payload: TemplateCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("notification:template:write"))],
                    x_correlation_id: Annotated[str | None, Header()] = None):
    try:
        service.validate_template(payload.subject_template, payload.body_template, payload.allowed_variables)
    except service.TemplateError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_notification_template", "message": str(exc)}) from None
    row = NotificationTemplate(organization_id=principal.organization_id, created_by=principal.subject, **payload.model_dump())
    db.add(row)
    try:
        db.flush()
        _audit(db, principal, "notification_template.created", "notification_template", row.id, {"code": row.code, "channel": row.channel}, x_correlation_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "notification_template_exists"}) from None
    return {"id": row.id, "code": row.code, "channel": row.channel, "allowed_variables": row.allowed_variables, "version": row.version}


@router.get("/templates")
def list_templates(db: Db, principal: Annotated[Principal, Depends(require_permission("notification:template:read"))]):
    rows = db.scalars(select(NotificationTemplate).where(NotificationTemplate.organization_id == principal.organization_id)).all()
    return [{"id": r.id, "code": r.code, "channel": r.channel, "subject_template": r.subject_template, "body_template": r.body_template,
             "allowed_variables": r.allowed_variables, "active": r.active} for r in rows]


@router.post("/send", status_code=202)
def send(payload: SendRequest, db: Db, principal: Annotated[Principal, Depends(require_permission("notification:send"))],
         x_correlation_id: Annotated[str | None, Header()] = None):
    try:
        message = service.enqueue(db, principal.organization_id, payload.recipient_subject, payload.template_code, payload.variables,
                                  payload.channel, payload.idempotency_key, x_correlation_id)
    except service.TemplateError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_notification_variables", "message": str(exc)}) from None
    if message is None:
        raise HTTPException(status_code=404, detail="Active notification template not found")
    _audit(db, principal, "notification.queued", "notification_message", message.id, {"template": message.template_code, "status": message.status}, x_correlation_id)
    db.commit()
    return dump(message)


@router.get("/messages")
def list_messages(db: Db, principal: Annotated[Principal, Depends(require_permission("notification:outbox:read"))],
                  status: str | None = Query(default=None, pattern="^(Pending|Sent|DeadLetter|Suppressed)$"), limit: int = Query(default=100, ge=1, le=500)):
    stmt = select(NotificationMessage).where(NotificationMessage.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(NotificationMessage.status == status)
    return [dump(m) for m in db.scalars(stmt.order_by(NotificationMessage.created_at.desc()).limit(limit)).all()]


@router.get("/status")
def outbox_status(db: Db, principal: Annotated[Principal, Depends(require_permission("notification:outbox:read"))]):
    return service.status_summary(db, principal.organization_id)


@router.post("/process")
def process(db: Db, principal: Annotated[Principal, Depends(require_permission("notification:process"))],
            provider: Annotated[NotificationProvider, Depends(get_notification_provider)], limit: int = Query(default=100, ge=1, le=500)):
    return service.process_due(db, provider, principal.organization_id, limit=limit)


@router.post("/messages/{message_id}/retry")
def retry(message_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("notification:process"))]):
    message = service.retry_dead_letter(db, principal.organization_id, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Dead-letter message not found")
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action="notification.dead_letter_retried",
                      entity_type="notification_message", entity_id=message.id, details={"template": message.template_code}))
    db.commit()
    return dump(message)


@router.get("/preferences/me")
def my_preferences(db: Db, principal: Annotated[Principal, Depends(get_principal)]):
    rows = {p.channel: p.enabled for p in db.scalars(select(NotificationPreference).where(
        NotificationPreference.organization_id == principal.organization_id, NotificationPreference.subject == principal.subject)).all()}
    return {channel: rows.get(channel, True) for channel in sorted(service.CHANNELS)}


@router.put("/preferences/me")
def set_my_preference(payload: PreferenceWrite, db: Db, principal: Annotated[Principal, Depends(get_principal)]):
    """A user may only change their own preferences; the subject always comes from the verified token."""
    pref = db.scalar(select(NotificationPreference).where(
        NotificationPreference.organization_id == principal.organization_id, NotificationPreference.subject == principal.subject,
        NotificationPreference.channel == payload.channel))
    if pref is None:
        pref = NotificationPreference(organization_id=principal.organization_id, subject=principal.subject, channel=payload.channel)
        db.add(pref)
    pref.enabled = payload.enabled
    pref.updated_at = service.utcnow()
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action="notification_preference.changed",
                      entity_type="notification_preference", entity_id=payload.channel, details={"channel": payload.channel, "enabled": payload.enabled}))
    db.commit()
    return {"channel": payload.channel, "enabled": pref.enabled}
