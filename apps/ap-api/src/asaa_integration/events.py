"""Ingest and list ecosystem events (asaa.event.v1). The envelope id is the idempotency key."""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_integration.alerts import notify_critical
from asaa_integration.models import IntegrationEvent

router = APIRouter(prefix="/api/v1/integration", tags=["Ecosystem Integration"])
Db = Annotated[Session, Depends(get_db)]

MAX_DATA_BYTES = 16 * 1024
MAX_DATA_DEPTH = 8
Project = Literal["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"]
Severity = Literal["info", "warning", "critical"]
_SECRET_KEY = re.compile(r"(password|passwd|pwd|secret|token|api[_-]?key|apikey|credential|authorization|private[_-]?key|bearer|cookie)", re.I)
# Usage counters such as LLM token counts are not credentials.
_ALLOWED_KEYS = re.compile(r"^(prompt|completion|input|output|total|cached)_tokens$|^tokens_(used|count|total)$", re.I)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventEnvelope(Strict):
    specversion: Literal["asaa.event.v1"]
    id: uuid.UUID
    source: str = Field(pattern=r"^[a-z][a-z0-9-]{1,39}$")
    type: str = Field(max_length=120, pattern=r"^(asaa|jarvis|templates|portfolio|ci)\.[a-z0-9-]+(\.[a-z0-9-]+){1,3}$")
    time: datetime
    orgId: str = Field(min_length=1, max_length=128)
    project: Project
    subject: str | None = Field(default=None, max_length=200)
    correlationId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{8,64}$")
    severity: Severity = "info"
    data: dict

    @field_validator("time")
    @classmethod
    def time_has_zone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("time must include a UTC offset (RFC 3339 date-time)")
        return value.astimezone(timezone.utc)


def secret_key_paths(value, path: str = "data", depth: int = 0) -> list[str]:
    """Paths of dictionary keys that look like credentials (values are never echoed)."""
    if depth > MAX_DATA_DEPTH:
        return [f"{path}: nesting too deep"]
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY.search(str(key)) and not _ALLOWED_KEYS.match(str(key)):
                found.append(f"{path}.{key}")
            found.extend(secret_key_paths(child, f"{path}.{key}", depth + 1))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(secret_key_paths(child, f"{path}[{index}]", depth + 1))
    return found


def dump(row: IntegrationEvent) -> dict:
    return {"id": row.id, "organization_id": row.organization_id, "source": row.source, "type": row.type, "project": row.project,
            "subject": row.subject, "correlation_id": row.correlation_id, "severity": row.severity,
            "occurred_at": row.occurred_at, "received_at": row.received_at, "data": row.data, "received_by": row.received_by}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _same_content(row: IntegrationEvent, envelope: EventEnvelope, org: str) -> bool:
    return (row.organization_id == org and row.source == envelope.source and row.type == envelope.type
            and row.project == envelope.project and row.subject == envelope.subject
            and row.correlation_id == envelope.correlationId and row.severity == envelope.severity
            and _utc(row.occurred_at) == _utc(envelope.time) and row.data == envelope.data)


@router.post("/events")
def ingest_event(envelope: EventEnvelope, response: Response, db: Db, principal: Annotated[Principal, Depends(require_permission("integration:event:write"))],
                 x_correlation_id: Annotated[str | None, Header()] = None):
    if envelope.orgId != principal.organization_id:
        raise HTTPException(status_code=403, detail={"code": "event_org_mismatch"})
    if len(json.dumps(envelope.data, separators=(",", ":"), default=str).encode()) > MAX_DATA_BYTES:
        raise HTTPException(status_code=422, detail={"code": "event_data_too_large", "message": "data exceeds 16 KiB"})
    secrets = secret_key_paths(envelope.data)
    if secrets:
        raise HTTPException(status_code=422, detail={"code": "event_data_contains_secret_like_key", "keys": secrets[:10]})
    event_id = str(envelope.id)

    def existing() -> dict | None:
        row = db.get(IntegrationEvent, event_id)
        if row is None:
            return None
        if _same_content(row, envelope, principal.organization_id):
            return {"status": "duplicate", "event": dump(row)}
        raise HTTPException(status_code=409, detail={"code": "event_id_conflict"})

    found = existing()
    if found:
        return found
    row = IntegrationEvent(id=event_id, organization_id=principal.organization_id, source=envelope.source, type=envelope.type,
                           project=envelope.project, subject=envelope.subject, correlation_id=envelope.correlationId,
                           severity=envelope.severity, occurred_at=envelope.time, data=envelope.data, received_by=principal.subject)
    correlation = x_correlation_id or envelope.correlationId
    try:
        db.add(row)
        db.flush()
        queued = notify_critical(db, row, correlation)
        db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action="integration_event.received",
                          entity_type="integration_event", entity_id=event_id,
                          details={"source": envelope.source, "type": envelope.type, "project": envelope.project, "severity": envelope.severity,
                                   "notifications_queued": queued},
                          correlation_id=correlation))
        db.commit()
    except IntegrityError:
        db.rollback()
        found = existing()
        if found:
            return found
        raise
    db.refresh(row)
    response.status_code = 201
    return {"status": "accepted", "event": dump(row)}


@router.get("/events")
def list_events(db: Db, principal: Annotated[Principal, Depends(require_permission("integration:event:read"))],
                source: str | None = Query(default=None, max_length=40), type: str | None = Query(default=None, max_length=120),
                project: Project | None = None, severity: Severity | None = None,
                limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    query = select(IntegrationEvent).where(IntegrationEvent.organization_id == principal.organization_id)
    for column, value in ((IntegrationEvent.source, source), (IntegrationEvent.type, type),
                          (IntegrationEvent.project, project), (IntegrationEvent.severity, severity)):
        if value is not None:
            query = query.where(column == value)
    rows = db.scalars(query.order_by(IntegrationEvent.occurred_at.desc(), IntegrationEvent.received_at.desc(), IntegrationEvent.id)
                      .limit(limit).offset(offset)).all()
    return [dump(row) for row in rows]
