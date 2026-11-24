"""Receivables: debit notes, receipt refunds and invoice disputes (ASAA-P1-09). All records trace to an invoice or receipt in the caller's organization.
Debit notes and refunds are maker-checker; a refund moves through Pending Approval -> Approved -> Refunded, where Refunded only records that payment was executed
elsewhere (no payment is initiated here). Disputes never change a balance. No tax or statutory numbering is applied (pending owner accounting policy)."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.ar_service import audit, invoice_clause, money, receipt_clause, receipt_unapplied
from asaa_ap.database import get_db
from asaa_ap.models import ARCreditNote, ARDebitNote, ARDispute, ARInvoice, ARReceipt, ARRefund
from asaa_ap.security import Principal, require_permission
from asaa_governance.scope import AccessScope, require_scoped_permission

router = APIRouter(prefix="/api/v1/ar", tags=["Accounts Receivable"])
Db = Annotated[Session, Depends(get_db)]
Corr = Annotated[str | None, Header()]
OPEN = ["Issued", "Partially Paid"]
Reason = Field(min_length=3, max_length=500)
Amount = Field(gt=0, max_digits=18, decimal_places=2)


class DebitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Amount
    reason: str = Reason


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Reason


class RefundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Amount
    reason: str = Reason


class RefundRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_reference: str = Field(min_length=1, max_length=200)


class DisputeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str = Field(min_length=1, max_length=36)
    disputed_amount: Decimal = Amount
    reason: str = Reason


class DisputeResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["Upheld", "Rejected"]
    note: str = Reason
    credit_note_id: str | None = Field(default=None, max_length=36)


def plain(row) -> dict:
    out = {}
    for k, v in row.__dict__.items():
        if k.startswith("_"):
            continue
        out[k] = str(v) if isinstance(v, Decimal) else (v.isoformat() if isinstance(v, datetime) else v)
    return out


def invoice_or_404(db: Session, invoice_id: str, org: str, lock: bool = False, scope: AccessScope | None = None) -> ARInvoice:
    """An invoice outside the caller's data scope is reported as not found."""
    stmt = select(ARInvoice).where(ARInvoice.id == invoice_id, ARInvoice.organization_id == org)
    if scope is not None:
        stmt = stmt.where(invoice_clause(scope))
    row = db.scalar(stmt.with_for_update() if lock else stmt)
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return row


def debit_clause(scope: AccessScope):
    return scope.clause(customer=ARDebitNote.customer_id, record=ARDebitNote.id)


def refund_clause(scope: AccessScope):
    return scope.clause(customer=ARRefund.customer_id, record=ARRefund.id)


def dispute_clause(scope: AccessScope):
    return scope.clause(customer=ARDispute.customer_id, record=ARDispute.id)


# ---- debit notes -------------------------------------------------------------------------------------------------------

@router.post("/debit-notes", status_code=201)
def create_debit_note(payload: DebitCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:debit:write"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:debit:write"))], x_correlation_id: Corr = None):
    invoice = invoice_or_404(db, payload.invoice_id, principal.organization_id, lock=True, scope=scope)
    if invoice.status not in OPEN:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_debitable", "status": invoice.status})
    row = ARDebitNote(organization_id=principal.organization_id, customer_id=invoice.customer_id, invoice_id=invoice.id, currency=invoice.currency,
                      amount=money(payload.amount), reason=payload.reason, created_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "debit_note.created", "ar_debit_note", row.id, {"invoice_id": invoice.id, "amount": str(row.amount)}, x_correlation_id)
    db.commit()
    return plain(row)


@router.get("/debit-notes")
def list_debit_notes(db: Db, principal: Annotated[Principal, Depends(require_permission("ar:debit:read"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:debit:read"))], status: str | None = None, invoice_id: str | None = None,
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ARDebitNote).where(ARDebitNote.organization_id == principal.organization_id, debit_clause(scope))
    if status:
        stmt = stmt.where(ARDebitNote.status == status)
    if invoice_id:
        stmt = stmt.where(ARDebitNote.invoice_id == invoice_id)
    return [plain(r) for r in db.scalars(stmt.order_by(ARDebitNote.created_at.desc()).offset(offset).limit(limit)).all()]


@router.post("/debit-notes/{note_id}/review")
def review_debit_note(note_id: str, payload: Review, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:debit:approve"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:debit:approve"))], x_correlation_id: Corr = None):
    note = db.scalar(select(ARDebitNote).where(ARDebitNote.id == note_id, ARDebitNote.organization_id == principal.organization_id, debit_clause(scope)).with_for_update())
    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")
    if note.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a debit note cannot approve it")
    if note.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "debit_note_not_pending"})
    note.reviewed_by, note.reviewed_at, note.review_reason = principal.subject, datetime.now(timezone.utc), payload.reason
    if payload.decision == "reject":
        note.status = "Rejected"
    else:
        invoice = invoice_or_404(db, note.invoice_id, principal.organization_id, lock=True)
        if invoice.status not in OPEN:
            raise HTTPException(status_code=409, detail={"code": "invoice_not_debitable", "status": invoice.status})
        note.status = "Approved"  # the balance grows; the invoice stays Issued or Partially Paid
    audit(db, principal, "debit_note.reviewed", "ar_debit_note", note.id, {"decision": payload.decision, "reason": payload.reason, "invoice_id": note.invoice_id}, x_correlation_id)
    db.commit()
    return plain(note)


# ---- refunds -----------------------------------------------------------------------------------------------------------

@router.post("/refunds", status_code=201)
def create_refund(payload: RefundCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:refund:write"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:refund:write"))], x_correlation_id: Corr = None):
    receipt = db.scalar(select(ARReceipt).where(ARReceipt.id == payload.receipt_id, ARReceipt.organization_id == principal.organization_id, receipt_clause(scope)).with_for_update())
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.status != "Recorded":
        raise HTTPException(status_code=409, detail={"code": "receipt_not_refundable", "status": receipt.status})
    unapplied = receipt_unapplied(db, receipt)
    if money(payload.amount) > unapplied:
        raise HTTPException(status_code=409, detail={"code": "refund_exceeds_unapplied_receipt", "unapplied_amount": str(unapplied)})
    row = ARRefund(organization_id=principal.organization_id, customer_id=receipt.customer_id, receipt_id=receipt.id, currency=receipt.currency,
                   amount=money(payload.amount), reason=payload.reason, created_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "refund.requested", "ar_refund", row.id, {"receipt_id": receipt.id, "amount": str(row.amount)}, x_correlation_id)
    db.commit()
    return plain(row)


@router.get("/refunds")
def list_refunds(db: Db, principal: Annotated[Principal, Depends(require_permission("ar:refund:read"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:refund:read"))], status: str | None = None, receipt_id: str | None = None,
                 limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ARRefund).where(ARRefund.organization_id == principal.organization_id, refund_clause(scope))
    if status:
        stmt = stmt.where(ARRefund.status == status)
    if receipt_id:
        stmt = stmt.where(ARRefund.receipt_id == receipt_id)
    return [plain(r) for r in db.scalars(stmt.order_by(ARRefund.created_at.desc()).offset(offset).limit(limit)).all()]


def locked_refund(db: Session, refund_id: str, org: str, scope: AccessScope) -> ARRefund:
    row = db.scalar(select(ARRefund).where(ARRefund.id == refund_id, ARRefund.organization_id == org, refund_clause(scope)).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Refund not found")
    return row


@router.post("/refunds/{refund_id}/review")
def review_refund(refund_id: str, payload: Review, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:refund:approve"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:refund:approve"))], x_correlation_id: Corr = None):
    row = locked_refund(db, refund_id, principal.organization_id, scope)
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a refund cannot approve it")
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "refund_not_pending"})
    row.status = "Approved" if payload.decision == "approve" else "Rejected"  # a rejection releases the reserved amount
    row.reviewed_by, row.reviewed_at, row.review_reason = principal.subject, datetime.now(timezone.utc), payload.reason
    audit(db, principal, "refund.reviewed", "ar_refund", row.id, {"decision": payload.decision, "reason": payload.reason, "receipt_id": row.receipt_id}, x_correlation_id)
    db.commit()
    return plain(row)


@router.post("/refunds/{refund_id}/record-payment")
def record_refund_payment(refund_id: str, payload: RefundRecord, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:refund:record"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:refund:record"))], x_correlation_id: Corr = None):
    """Record that an approved refund was paid out through the bank or provider (outside ASAA). Separate permission and a person other than the approver."""
    row = locked_refund(db, refund_id, principal.organization_id, scope)
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "refund_not_approved"})
    if principal.subject in {row.created_by, row.reviewed_by}:
        raise HTTPException(status_code=403, detail="The maker or approver of a refund cannot record its payment")
    row.status, row.refunded_by, row.refunded_at, row.payment_reference = "Refunded", principal.subject, datetime.now(timezone.utc), payload.payment_reference
    audit(db, principal, "refund.payment_recorded", "ar_refund", row.id, {"receipt_id": row.receipt_id, "amount": str(row.amount), "payment_reference": payload.payment_reference}, x_correlation_id)
    db.commit()
    return plain(row)


# ---- disputes ----------------------------------------------------------------------------------------------------------

@router.post("/disputes", status_code=201)
def raise_dispute(payload: DisputeCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:dispute:write"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:dispute:write"))], x_correlation_id: Corr = None):
    invoice = invoice_or_404(db, payload.invoice_id, principal.organization_id, scope=scope)
    if invoice.status in {"Draft", "Void"}:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_disputable", "status": invoice.status})
    if money(payload.disputed_amount) > invoice.total:
        raise HTTPException(status_code=409, detail={"code": "dispute_exceeds_invoice_total", "invoice_total": str(invoice.total)})
    row = ARDispute(organization_id=principal.organization_id, customer_id=invoice.customer_id, invoice_id=invoice.id, currency=invoice.currency,
                    disputed_amount=money(payload.disputed_amount), reason=payload.reason, created_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "dispute.raised", "ar_dispute", row.id, {"invoice_id": invoice.id, "disputed_amount": str(row.disputed_amount)}, x_correlation_id)
    db.commit()
    return plain(row)


@router.get("/disputes")
def list_disputes(db: Db, principal: Annotated[Principal, Depends(require_permission("ar:dispute:read"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:dispute:read"))], status: str | None = None, invoice_id: str | None = None,
                  limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ARDispute).where(ARDispute.organization_id == principal.organization_id, dispute_clause(scope))
    if status:
        stmt = stmt.where(ARDispute.status == status)
    if invoice_id:
        stmt = stmt.where(ARDispute.invoice_id == invoice_id)
    return [plain(r) for r in db.scalars(stmt.order_by(ARDispute.created_at.desc()).offset(offset).limit(limit)).all()]


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, payload: DisputeResolve, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:dispute:resolve"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:dispute:resolve"))], x_correlation_id: Corr = None):
    row = db.scalar(select(ARDispute).where(ARDispute.id == dispute_id, ARDispute.organization_id == principal.organization_id, dispute_clause(scope)).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The person who raised a dispute cannot resolve it")
    if row.status != "Open":
        raise HTTPException(status_code=409, detail={"code": "dispute_not_open"})
    if payload.credit_note_id:
        if payload.outcome != "Upheld" or not db.scalar(select(ARCreditNote.id).where(
                ARCreditNote.id == payload.credit_note_id, ARCreditNote.organization_id == principal.organization_id, ARCreditNote.invoice_id == row.invoice_id)):
            raise HTTPException(status_code=409, detail={"code": "credit_note_not_valid_for_dispute"})
    row.status, row.resolved_by, row.resolved_at = payload.outcome, principal.subject, datetime.now(timezone.utc)
    row.resolution_note, row.credit_note_id = payload.note, payload.credit_note_id
    audit(db, principal, "dispute.resolved", "ar_dispute", row.id, {"outcome": payload.outcome, "invoice_id": row.invoice_id, "credit_note_id": payload.credit_note_id}, x_correlation_id)
    db.commit()
    return plain(row)


@router.post("/disputes/{dispute_id}/withdraw")
def withdraw_dispute(dispute_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:dispute:write"))], scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:dispute:write"))], x_correlation_id: Corr = None):
    row = db.scalar(select(ARDispute).where(ARDispute.id == dispute_id, ARDispute.organization_id == principal.organization_id, dispute_clause(scope)).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if row.status != "Open":
        raise HTTPException(status_code=409, detail={"code": "dispute_not_open"})
    row.status, row.resolved_by, row.resolved_at = "Withdrawn", principal.subject, datetime.now(timezone.utc)
    audit(db, principal, "dispute.withdrawn", "ar_dispute", row.id, {"invoice_id": row.invoice_id}, x_correlation_id)
    db.commit()
    return plain(row)
