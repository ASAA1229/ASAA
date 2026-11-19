"""Ingest and list ecosystem events (asaa.event.v1). (organization, envelope id) is the idempotency key.

Defences, in order: permission, per-principal rate limit, correlation header, bounded body, JSON parse without NaN/Infinity and with
a depth guard, envelope validation, organization binding, producer binding (token azp -> allowed source/project/type prefix),
payload size, credential screening, timestamp window, server-side severity policy. Rejections of the security-relevant kind
(403, 409, 422) are audited without the payload.
"""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.config import get_settings
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_integration import screening
from asaa_integration.alerts import notify_critical
from asaa_integration.models import IntegrationEvent

router = APIRouter(prefix="/api/v1/integration", tags=["Ecosystem Integration"])
Db = Annotated[Session, Depends(get_db)]

MAX_DATA_BYTES = 16 * 1024
MAX_BODY_BYTES = 32 * 1024  # envelope plus data; the ASGI hardening layer enforces the same limit on the wire
Project = Literal["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"]
Severity = Literal["info", "warning", "critical"]
CORRELATION = re.compile(r"^[A-Za-z0-9._-]{8,64}\Z")
SECURITY_SEGMENT = "security"


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
    subject: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:/-]{1,200}$")
    correlationId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{8,64}$")
    severity: Severity = "info"
    data: dict

    @field_validator("time")
    @classmethod
    def time_has_zone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("time must include a UTC offset (RFC 3339 date-time)")
        try:
            return value.astimezone(timezone.utc)
        except (OverflowError, ValueError):
            raise ValueError("time is out of range") from None


# ---------------------------------------------------------------- severity policy

def effective_severity(event_type: str, declared: str) -> str:
    """Only security events (`<producer>.security.<name>`) may be critical; any other type is capped at warning."""
    parts = event_type.split(".")
    if declared == "critical" and not (len(parts) > 2 and parts[1] == SECURITY_SEGMENT):
        return "warning"
    return declared


# ---------------------------------------------------------------- rate limit (token bucket, per process)

_bucket_lock = threading.Lock()
_buckets: dict[tuple, list] = {}
_now = time.monotonic


def reset_rate_limits() -> None:
    with _bucket_lock:
        _buckets.clear()


def take_token(key: tuple, per_minute: int, burst: int) -> float | None:
    """Consume one token; returns None when allowed, else the seconds until a token is available."""
    rate = per_minute / 60.0
    now = _now()
    with _bucket_lock:
        if len(_buckets) > 10000:  # bound memory: forget the idlest principals
            for stale in sorted(_buckets, key=lambda k: _buckets[k][1])[:5000]:
                del _buckets[stale]
        tokens, last = _buckets.get(key, [float(burst), now])
        tokens = min(float(burst), tokens + (now - last) * rate)
        if tokens >= 1.0:
            _buckets[key] = [tokens - 1.0, now]
            return None
        _buckets[key] = [tokens, now]
        return (1.0 - tokens) / rate


# ---------------------------------------------------------------- helpers

def dump(row: IntegrationEvent) -> dict:
    return {"id": row.id, "organization_id": row.organization_id, "source": row.source, "type": row.type, "project": row.project,
            "subject": row.subject, "correlation_id": row.correlation_id, "severity": row.severity,
            "declared_severity": row.declared_severity, "occurred_at": row.occurred_at, "received_at": row.received_at,
            "data": row.data, "received_by": row.received_by}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _same_content(row: IntegrationEvent, envelope: EventEnvelope, org: str) -> bool:
    return (row.organization_id == org and row.source == envelope.source and row.type == envelope.type
            and row.project == envelope.project and row.subject == envelope.subject
            and row.correlation_id == envelope.correlationId and row.declared_severity == envelope.severity
            and _utc(row.occurred_at) == _utc(envelope.time) and row.data == envelope.data)


def _reject(db: Session, principal: Principal, status: int, code: str, correlation: str | None, event_id: str | None = None,
            extra: dict | None = None, headers: dict | None = None, audit: bool = True):
    """Record the rejection (reason code and caller only, never the payload) and raise the HTTP error."""
    if audit:
        db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action="integration_event.rejected",
                          entity_type="integration_event", entity_id=event_id or "-", outcome="failure",
                          details={"reason": code, "status": status, "client_id": principal.client_id, **(extra or {})},
                          correlation_id=correlation))
        db.commit()
    detail = {"code": code, **(extra or {})}
    raise HTTPException(status_code=status, detail=detail, headers=headers)


def _correlation(request: Request) -> tuple[str | None, bool]:
    """(value, valid). X-Correlation-ID wins over X-Request-ID; a present but malformed header is invalid."""
    for name in ("x-correlation-id", "x-request-id"):
        value = request.headers.get(name)
        if value is not None:
            return (value, True) if CORRELATION.match(value) else (None, False)
    return None, True


def _peek_event_id(document) -> str | None:
    value = document.get("id") if isinstance(document, dict) else None
    try:
        return str(uuid.UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def _parse(raw: bytes):
    def refuse(constant):
        raise ValueError("non-finite number")

    return json.loads(raw, parse_constant=refuse)


# ---------------------------------------------------------------- endpoints

WRITER = require_permission("integration:event:write")


async def limited_body(request: Request, principal: Annotated[Principal, Depends(WRITER)]) -> bytes:
    """Runs after the permission check: applies the per-principal rate limit, then reads the (wire-limited) body asynchronously so
    the synchronous handler can use the database from the thread pool."""
    settings = get_settings()
    wait = take_token((principal.organization_id, principal.subject, principal.client_id), settings.integration_rate_per_minute,
                      settings.integration_rate_burst)
    if wait is not None:
        raise HTTPException(status_code=429, detail={"code": "event_rate_limited"}, headers={"Retry-After": str(max(1, int(wait + 0.999)))})
    return await request.body()


@router.post("/events")
def ingest_event(raw: Annotated[bytes, Depends(limited_body)], request: Request, response: Response, db: Db,
                 principal: Annotated[Principal, Depends(WRITER)]):
    settings = get_settings()
    correlation, valid = _correlation(request)
    if not valid:
        _reject(db, principal, 422, "invalid_correlation_id", None)
    if len(raw) > MAX_BODY_BYTES:
        _reject(db, principal, 413, "event_too_large", correlation)
    try:
        document = _parse(raw)
    except (ValueError, RecursionError):
        _reject(db, principal, 422, "invalid_json", correlation)
    event_id = _peek_event_id(document)
    if screening.depth_of(document) > screening.MAX_DEPTH:
        _reject(db, principal, 422, "event_too_deeply_nested", correlation, event_id)
    if screening.has_non_finite(document):
        _reject(db, principal, 422, "event_data_non_finite_number", correlation, event_id)
    try:
        envelope = EventEnvelope.model_validate(document)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})[:10]
        _reject(db, principal, 422, "invalid_event", correlation, event_id, {"fields": fields})
    correlation = correlation or envelope.correlationId
    if envelope.orgId != principal.organization_id:
        _reject(db, principal, 403, "event_org_mismatch", correlation, event_id)
    mapping = settings.integration_producers.get(principal.client_id or "")
    if mapping is None:
        _reject(db, principal, 403, "producer_not_authorized", correlation, event_id)
    if (envelope.source != mapping.source or envelope.project != mapping.project
            or not envelope.type.startswith(mapping.typePrefix)):
        _reject(db, principal, 403, "producer_mismatch", correlation, event_id)
    if len(json.dumps(envelope.data, separators=(",", ":"), default=str).encode()) > MAX_DATA_BYTES:
        _reject(db, principal, 422, "event_data_too_large", correlation, event_id)
    findings = screening.screen(envelope.data)
    if findings:
        _reject(db, principal, 422, "event_data_contains_secret_like_content", correlation, event_id, {"findings": findings[:10]})
    skew = timedelta(seconds=settings.integration_clock_skew_seconds)
    now = datetime.now(timezone.utc)
    if not (now - skew <= envelope.time <= now + skew):
        _reject(db, principal, 422, "event_time_out_of_range", correlation, event_id)
    event_key = str(envelope.id)
    org = principal.organization_id

    def existing() -> dict | None:
        row = db.get(IntegrationEvent, (event_key, org))
        if row is None:
            return None
        if _same_content(row, envelope, org):
            return {"status": "duplicate", "event": dump(row)}
        _reject(db, principal, 409, "event_id_conflict", correlation, event_key)

    found = existing()
    if found:
        return found
    row = IntegrationEvent(id=event_key, organization_id=org, source=envelope.source, type=envelope.type, project=envelope.project,
                           subject=envelope.subject, correlation_id=envelope.correlationId,
                           severity=effective_severity(envelope.type, envelope.severity), declared_severity=envelope.severity,
                           occurred_at=envelope.time, data=envelope.data, received_by=principal.subject)
    try:
        db.add(row)
        db.flush()
        queued = notify_critical(db, row, correlation)
        db.add(AuditEvent(organization_id=org, actor_id=principal.subject, action="integration_event.received",
                          entity_type="integration_event", entity_id=event_key,
                          details={"source": envelope.source, "type": envelope.type, "project": envelope.project,
                                   "severity": row.severity, "declared_severity": row.declared_severity,
                                   "client_id": principal.client_id, "notifications_queued": queued},
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
