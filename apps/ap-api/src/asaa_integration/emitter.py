"""ASAA-originated ecosystem events (asaa.event.v1), written to the same store that ingested events use.

Events are staged in the caller's database session (transactional outbox style): they commit or roll back together with the state
change and its audit record. Only actions listed in EMITTED are emitted, and only the listed detail keys are copied, so an event can
never carry free text, reasons, evidence, names, e-mail addresses or any other personal data: it identifies the record (opaque id),
the action and its non-personal outcome. Data is screened by the same credential screening as inbound events; a finding drops the
event rather than risk leaking, and the audit record is unaffected.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from asaa_ap.models import AuditEvent
from asaa_integration import screening
from asaa_integration.models import IntegrationEvent

logger = logging.getLogger("asaa.events")

# audit action -> (event type, entity path used as the envelope subject, allowed detail keys)
EMITTED: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "purchase_order.created": ("asaa.payables.purchase-order-created", "purchase-order", ("currency", "total")),
    "purchase_order.reviewed": ("asaa.payables.purchase-order-reviewed", "purchase-order", ("decision",)),
    "purchase_order.issued": ("asaa.payables.purchase-order-issued", "purchase-order", ()),
    "purchase_order.cancelled": ("asaa.payables.purchase-order-cancelled", "purchase-order", ()),
    "goods_receipt.recorded": ("asaa.payables.goods-receipt-recorded", "goods-receipt", ("line_count",)),
    "supplier_invoice.captured": ("asaa.payables.supplier-invoice-captured", "supplier-invoice", ("currency", "total")),
    "supplier_invoice.matched": ("asaa.payables.supplier-invoice-matched", "supplier-invoice", ("outcome",)),
    "supplier_invoice.reviewed": ("asaa.payables.supplier-invoice-reviewed", "supplier-invoice", ("decision", "exception_override")),
    "payment_batch.created": ("asaa.payables.payment-batch-created", "payment-batch", ("currency", "total", "invoice_count")),
    "payment_batch.approved": ("asaa.payables.payment-batch-approved", "payment-batch", ("total",)),
    "payment_batch.cancelled": ("asaa.payables.payment-batch-cancelled", "payment-batch", ()),
    "payment_batch.payment_recorded": ("asaa.payables.payment-recorded", "payment-batch", ("total",)),
    "credit_note.created": ("asaa.receivables.credit-note-created", "credit-note", ("amount",)),
    "credit_note.reviewed": ("asaa.receivables.credit-note-reviewed", "credit-note", ("decision",)),
    "invoice.voided": ("asaa.receivables.invoice-voided", "ar-invoice", ("total",)),
    "attendance_correction.requested": ("asaa.attendance.correction-requested", "attendance-correction", ()),
    "attendance_correction.reviewed": ("asaa.attendance.correction-reviewed", "attendance-correction", ("decision",)),
    "attendance.overtime_reviewed": ("asaa.attendance.overtime-reviewed", "attendance-record", ("decision",)),
    "attendance_policy.approved": ("asaa.attendance.policy-approved", "attendance-policy", ()),
    "service.reviewed": ("asaa.delivery.service-reviewed", "service", ("decision",)),
    "engagement.created": ("asaa.delivery.engagement-created", "engagement", ()),
    "engagement.status_changed": ("asaa.delivery.engagement-status-changed", "engagement", ("from", "to")),
    "milestone.delivered": ("asaa.delivery.milestone-delivered", "milestone", ()),
    "milestone.acceptance_recorded": ("asaa.delivery.milestone-acceptance-recorded", "milestone", ("decision",)),
    "milestone.invoice_linked": ("asaa.delivery.milestone-invoice-linked", "milestone", ()),
    "work_order.assigned": ("asaa.delivery.work-order-assigned", "work-order", ()),
    "work_order.completed": ("asaa.delivery.work-order-completed", "work-order", ()),
    "work_order.verified": ("asaa.delivery.work-order-verified", "work-order", ("decision",)),
    "expense.reviewed": ("asaa.expenses.claim-reviewed", "expense-claim", ("status",)),
    "expense_policy.approved": ("asaa.expenses.policy-approved", "expense-policy", ()),
    "expense_claim.policy_flagged": ("asaa.expenses.claim-policy-flagged", "expense-claim", ("rule",)),
    "offboarding.deprovisioning_requested": ("asaa.people.deprovisioning-requested", "exit-case", ()),
}


RETRY_PENDING = "ecosystem_event.retry_pending"
RETRY_SETTLED = "ecosystem_event.retry_settled"  # details: pending_id, result in (staged, exhausted, dropped)
RETRY_FAILED = "ecosystem_event.retry_failed"  # details: pending_id; one row per failed attempt


def _record_retry(db: Session, org: str, action: str, entity_id: str, data: dict, event_id: str, correlation_id: str | None) -> None:
    """Durable retry marker for an event that could not be staged: an append-only audit row holding only the allowlisted, screened
    event data, so a later sweep (asaa_integration.retry.process_due) can stage the same event. Never raises."""
    try:
        with db.begin_nested():
            db.add(AuditEvent(organization_id=org, actor_id="system:integration-outbox", action=RETRY_PENDING, entity_type="integration_event",
                              entity_id=event_id, outcome="pending", correlation_id=correlation_id,
                              details={"source_action": action, "source_entity_id": entity_id, "event_data": data}))
    except Exception:  # noqa: BLE001 - best effort; the business audit row remains the durable record
        logger.exception("ecosystem_event_retry_record_failed", extra={"action": action})


def emit_for_audit(db: Session, org: str, actor: str, action: str, entity_id: str, details: dict, correlation_id: str | None) -> bool:
    """Stage an event for an audited action if it is in the allowlist. Never raises; returns whether an event was staged.
    A failed stage is not lost: a retry marker is written (see asaa_integration.retry) and the business transaction proceeds."""
    spec = EMITTED.get(action)
    if spec is None:
        return False
    event_type, entity_path, keys = spec
    data = {"action": action.split(".", 1)[1].replace("_", "-"), "entityId": entity_id}
    for key in keys:
        if key in details and isinstance(details[key], (str, int, float, bool)) and details[key] is not None:
            data[key] = details[key] if not isinstance(details[key], float) else str(details[key])
    if screening.screen(data):
        logger.warning("ecosystem_event_dropped", extra={"event_type": event_type, "reason": "screening"})
        return False
    correlation = correlation_id if correlation_id and re.fullmatch(r"[A-Za-z0-9._-]{8,64}", correlation_id) else None
    event_id = str(uuid.uuid4())
    try:
        now = datetime.now(timezone.utc)
        # A savepoint isolates the event insert: if it fails, only the event is rolled back; the business change and its audit record stay in the transaction.
        with db.begin_nested():
            db.add(IntegrationEvent(id=event_id, organization_id=org, source="asaa", type=event_type, project="ASAA",
                                    subject=f"{entity_path}/{entity_id}"[:200], correlation_id=correlation, severity="info", declared_severity="info",
                                    occurred_at=now, received_at=now, data=data, received_by="asaa-internal"))
    except Exception:  # an event must never break the business transaction
        logger.exception("ecosystem_event_stage_failed", extra={"event_type": event_type, "action": action})
        _record_retry(db, org, action, entity_id, data, event_id, correlation)
        return False
    return True
