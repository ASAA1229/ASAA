"""Durable retry for ASAA-originated ecosystem events that could not be staged (outbox sweep).

A failed stage leaves an append-only audit row (ecosystem_event.retry_pending) holding the allowlisted, screened event data. This
sweep stages the same event (same id, so it is idempotent) with exponential backoff and records every outcome as a further audit
row: retry_failed per failed attempt and retry_settled when staged, exhausted or dropped. Audit rows are never updated. It runs
outside any business transaction (scheduled script), so it can never block one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.models import AuditEvent
from asaa_integration import screening
from asaa_integration.emitter import EMITTED, RETRY_FAILED, RETRY_PENDING, RETRY_SETTLED
from asaa_integration.models import IntegrationEvent

log = logging.getLogger("asaa.events")
MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 3600


def backoff_seconds(attempts: int) -> int:
    return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1)))


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _audit(db: Session, pending: AuditEvent, action: str, outcome: str, **details) -> None:
    db.add(AuditEvent(organization_id=pending.organization_id, actor_id="system:integration-outbox", action=action, entity_type="integration_event",
                      entity_id=pending.entity_id, outcome=outcome, correlation_id=pending.correlation_id,
                      details={"pending_id": pending.id, **details}))


def outstanding(db: Session, organization_id: str | None = None, limit: int = 500) -> list[AuditEvent]:
    """Pending markers with no settle row, oldest first."""
    stmt = select(AuditEvent).where(AuditEvent.action == RETRY_PENDING)
    if organization_id:
        stmt = stmt.where(AuditEvent.organization_id == organization_id)
    pendings = db.scalars(stmt.order_by(AuditEvent.created_at).limit(limit)).all()
    if not pendings:
        return []
    settled = {row.details.get("pending_id") for row in db.scalars(select(AuditEvent).where(
        AuditEvent.action == RETRY_SETTLED, AuditEvent.entity_id.in_([p.entity_id for p in pendings])))}
    return [p for p in pendings if p.id not in settled]


def process_due(db: Session, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    summary = {"processed": 0, "staged": 0, "retry_scheduled": 0, "exhausted": 0, "dropped": 0, "waiting": 0}
    for pending in outstanding(db, limit=limit):
        failures = [f for f in db.scalars(select(AuditEvent).where(AuditEvent.action == RETRY_FAILED, AuditEvent.entity_id == pending.entity_id)
                                          .order_by(AuditEvent.created_at)).all() if f.details.get("pending_id") == pending.id]
        if failures and now < _aware(failures[-1].created_at) + timedelta(seconds=backoff_seconds(len(failures))):
            summary["waiting"] += 1
            continue
        summary["processed"] += 1
        data = pending.details.get("event_data") or {}
        spec = EMITTED.get(pending.details.get("source_action"))
        if spec is None or screening.screen(data):
            _audit(db, pending, RETRY_SETTLED, "failure", result="dropped")
            summary["dropped"] += 1
            continue
        try:
            with db.begin_nested():
                if db.get(IntegrationEvent, (pending.entity_id, pending.organization_id)) is None:
                    db.add(IntegrationEvent(id=pending.entity_id, organization_id=pending.organization_id, source="asaa", type=spec[0], project="ASAA",
                                            subject=f"{spec[1]}/{pending.details.get('source_entity_id')}"[:200], severity="info",
                                            declared_severity="info", occurred_at=_aware(pending.created_at), received_at=now, data=data,
                                            received_by="asaa-internal"))
            _audit(db, pending, RETRY_SETTLED, "success", result="staged", attempts=len(failures) + 1)
            summary["staged"] += 1
        except Exception as exc:  # noqa: BLE001
            log.error("ecosystem_event_retry_failed", extra={"event_id": pending.entity_id, "error_type": type(exc).__name__})
            _audit(db, pending, RETRY_FAILED, "failure", error_type=type(exc).__name__, attempt=len(failures) + 1)
            if len(failures) + 1 >= MAX_ATTEMPTS:
                _audit(db, pending, RETRY_SETTLED, "failure", result="exhausted", attempts=len(failures) + 1)
                summary["exhausted"] += 1
            else:
                summary["retry_scheduled"] += 1
    db.commit()
    return summary
