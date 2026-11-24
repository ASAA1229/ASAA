"""Receivables: credit notes (maker-checker), invoice void, ageing and customer statements.

A credit note reduces the balance of one issued invoice only when approved by someone other than its maker. Credit notes are
internal balance adjustments: no tax recalculation or statutory credit-note numbering is applied (pending owner accounting policy).
Ageing buckets are a reporting convention and never convert currencies.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.ar_service import amount_credited, amount_debited, amount_paid, audit, get_customer, money, net_credit, settled_status
from asaa_ap.database import get_db
from asaa_ap.models import ARCreditNote, ARDebitNote, ARInvoice, ARReceipt, ARRefund
from asaa_ap.org_time import org_today
from asaa_ap.security import Principal, require_permission
from asaa_governance.scope import AccessScope, require_scoped_permission

router = APIRouter(prefix="/api/v1/ar", tags=["Accounts Receivable"])
Db = Annotated[Session, Depends(get_db)]
Corr = Annotated[str | None, Header()]
BUCKETS = (("current", None, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, None))
OPEN = ["Issued", "Partially Paid"]


class CreditNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str = Field(min_length=1, max_length=36)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)


class CreditNoteReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class VoidInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


def dump(c: ARCreditNote) -> dict:
    return {"id": c.id, "customer_id": c.customer_id, "invoice_id": c.invoice_id, "currency": c.currency, "amount": str(c.amount), "reason": c.reason, "status": c.status,
            "created_at": c.created_at.isoformat(), "created_by": c.created_by, "reviewed_by": c.reviewed_by, "review_reason": c.review_reason}


def locked_invoice(db: Session, invoice_id: str, org: str) -> ARInvoice:
    row = db.scalar(select(ARInvoice).where(ARInvoice.id == invoice_id, ARInvoice.organization_id == org).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return row


@router.post("/credit-notes", status_code=201)
def create_credit_note(payload: CreditNoteCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:credit:write"))], x_correlation_id: Corr = None):
    invoice = locked_invoice(db, payload.invoice_id, principal.organization_id)
    if invoice.status not in OPEN:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_creditable", "status": invoice.status})
    pending = sum((c.amount for c in db.scalars(select(ARCreditNote).where(ARCreditNote.invoice_id == invoice.id, ARCreditNote.status == "Pending Approval"))), Decimal("0"))
    outstanding = money(invoice.total - amount_paid(db, invoice.id) - net_credit(db, invoice.id))
    if money(payload.amount) + pending > outstanding:
        raise HTTPException(status_code=409, detail={"code": "credit_exceeds_outstanding", "outstanding_amount": str(outstanding), "pending_credit_amount": str(pending)})
    row = ARCreditNote(organization_id=principal.organization_id, customer_id=invoice.customer_id, invoice_id=invoice.id, currency=invoice.currency,
                       amount=money(payload.amount), reason=payload.reason, status="Pending Approval", created_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "credit_note.created", "ar_credit_note", row.id, {"invoice_id": invoice.id, "amount": str(row.amount)}, x_correlation_id)
    db.commit()
    return dump(row)


@router.get("/credit-notes")
def list_credit_notes(db: Db, principal: Annotated[Principal, Depends(require_permission("ar:credit:read"))], status: str | None = None, invoice_id: str | None = None,
                      limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ARCreditNote).where(ARCreditNote.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(ARCreditNote.status == status)
    if invoice_id:
        stmt = stmt.where(ARCreditNote.invoice_id == invoice_id)
    return [dump(c) for c in db.scalars(stmt.order_by(ARCreditNote.created_at.desc()).offset(offset).limit(limit)).all()]


@router.post("/credit-notes/{credit_id}/review")
def review_credit_note(credit_id: str, payload: CreditNoteReview, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:credit:approve"))], x_correlation_id: Corr = None):
    note = db.scalar(select(ARCreditNote).where(ARCreditNote.id == credit_id, ARCreditNote.organization_id == principal.organization_id).with_for_update())
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    if note.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a credit note cannot approve it")
    if note.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "credit_note_not_pending"})
    note.reviewed_by, note.reviewed_at, note.review_reason = principal.subject, datetime.now(timezone.utc), payload.reason
    if payload.decision == "reject":
        note.status = "Rejected"
    else:
        invoice = locked_invoice(db, note.invoice_id, principal.organization_id)
        paid, credited = amount_paid(db, invoice.id), net_credit(db, invoice.id)
        if invoice.status not in OPEN or note.amount > money(invoice.total - paid - credited):
            raise HTTPException(status_code=409, detail={"code": "credit_exceeds_outstanding", "outstanding_amount": str(money(invoice.total - paid - credited))})
        note.status = "Approved"
        db.flush()
        invoice.status = settled_status(invoice.total, paid, money(credited + note.amount))
    audit(db, principal, "credit_note.reviewed", "ar_credit_note", note.id, {"decision": payload.decision, "reason": payload.reason, "invoice_id": note.invoice_id}, x_correlation_id)
    db.commit()
    return dump(note)


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: str, payload: VoidInvoice, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:invoice:void"))], x_correlation_id: Corr = None):
    invoice = locked_invoice(db, invoice_id, principal.organization_id)
    if invoice.status != "Issued":
        raise HTTPException(status_code=409, detail={"code": "invoice_not_voidable", "status": invoice.status,
                                                     "message": "Only an Issued invoice with no receipts or credits can be voided; use a credit note otherwise"})
    if amount_paid(db, invoice.id) != 0 or amount_credited(db, invoice.id) != 0 or amount_debited(db, invoice.id) != 0 or db.scalar(select(ARCreditNote.id).where(ARCreditNote.invoice_id == invoice.id, ARCreditNote.status == "Pending Approval").limit(1)) or db.scalar(select(ARDebitNote.id).where(ARDebitNote.invoice_id == invoice.id, ARDebitNote.status == "Pending Approval").limit(1)):
        raise HTTPException(status_code=409, detail={"code": "invoice_has_settlements"})
    invoice.status = "Void"
    audit(db, principal, "invoice.voided", "ar_invoice", invoice.id, {"reason": payload.reason, "total": str(invoice.total)}, x_correlation_id)
    db.commit()
    return {"id": invoice.id, "status": invoice.status}


def open_balances(db: Session, org: str, customer_id: str | None = None) -> list[tuple[ARInvoice, Decimal]]:
    stmt = select(ARInvoice).where(ARInvoice.organization_id == org, ARInvoice.status.in_(OPEN))
    if customer_id:
        stmt = stmt.where(ARInvoice.customer_id == customer_id)
    return [(i, money(i.total - amount_paid(db, i.id) - net_credit(db, i.id))) for i in db.scalars(stmt).all()]


@router.get("/aging")
def receivables_aging(db: Db, principal: Annotated[Principal, Depends(require_permission("ar:invoice:read"))], as_of: date | None = None, customer_id: str | None = None):
    as_of = as_of or org_today(db, principal.organization_id)
    out: dict[str, dict] = {}
    for invoice, balance in open_balances(db, principal.organization_id, customer_id):
        days = (as_of - invoice.due_date).days
        label = next(n for n, lo, hi in BUCKETS if (lo is None or days >= lo) and (hi is None or days <= hi))
        b = out.setdefault(invoice.currency, {n: "0.00" for n, _, _ in BUCKETS} | {"total": "0.00", "invoice_count": 0})
        b[label] = str(money(Decimal(b[label]) + balance))
        b["total"] = str(money(Decimal(b["total"]) + balance))
        b["invoice_count"] += 1
    return {"as_of": as_of.isoformat(), "generated_at": datetime.now(timezone.utc).isoformat(), "sources": ["ar_invoices", "ar_receipt_allocations", "ar_credit_notes", "ar_debit_notes"],
            "by_currency": out, "note": "Outstanding = total less recorded receipts and approved credit notes, plus approved debit notes. Bucket boundaries are a reporting convention, not a payment-terms rule."}


@router.get("/customers/{customer_id}/statement")
def customer_statement(customer_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ar:invoice:read"))],
                       scope: Annotated[AccessScope, Depends(require_scoped_permission("ar:invoice:read"))], date_from: date | None = None, date_to: date | None = None):
    """Chronological invoices, receipts and approved credits with a running balance per currency."""
    org = principal.organization_id
    get_customer(db, customer_id, org, scope)
    entries: list[dict] = []
    for inv in db.scalars(select(ARInvoice).where(ARInvoice.organization_id == org, ARInvoice.customer_id == customer_id, ARInvoice.status.in_(["Issued", "Partially Paid", "Paid", "Credited"]))):
        entries.append({"date": inv.issue_date, "type": "invoice", "reference": inv.invoice_number or inv.id, "currency": inv.currency, "amount": inv.total})
    for rec in db.scalars(select(ARReceipt).where(ARReceipt.organization_id == org, ARReceipt.customer_id == customer_id, ARReceipt.status == "Recorded")):
        entries.append({"date": rec.received_date, "type": "receipt", "reference": rec.reference or rec.id, "currency": rec.currency, "amount": -rec.amount})
    for note in db.scalars(select(ARCreditNote).where(ARCreditNote.organization_id == org, ARCreditNote.customer_id == customer_id, ARCreditNote.status == "Approved")):
        entries.append({"date": (note.reviewed_at or note.created_at).date(), "type": "credit_note", "reference": note.id, "currency": note.currency, "amount": -note.amount})
    for dn in db.scalars(select(ARDebitNote).where(ARDebitNote.organization_id == org, ARDebitNote.customer_id == customer_id, ARDebitNote.status == "Approved")):
        entries.append({"date": (dn.reviewed_at or dn.created_at).date(), "type": "debit_note", "reference": dn.id, "currency": dn.currency, "amount": dn.amount})
    for rf in db.scalars(select(ARRefund).where(ARRefund.organization_id == org, ARRefund.customer_id == customer_id, ARRefund.status == "Refunded")):
        entries.append({"date": (rf.refunded_at or rf.created_at).date(), "type": "refund", "reference": rf.payment_reference or rf.id, "currency": rf.currency, "amount": rf.amount})
    entries.sort(key=lambda e: (e["date"], e["type"]))
    running: dict[str, Decimal] = {}
    rows = []
    for e in entries:
        running[e["currency"]] = money(running.get(e["currency"], Decimal("0")) + e["amount"])
        if (date_from and e["date"] < date_from) or (date_to and e["date"] > date_to):
            continue
        rows.append({**e, "date": e["date"].isoformat(), "amount": str(e["amount"]), "running_balance": str(running[e["currency"]])})
    return {"customer_id": customer_id, "generated_at": datetime.now(timezone.utc).isoformat(), "entries": rows,
            "closing_balance_by_currency": {c: str(v) for c, v in running.items()},
            "note": "Receipts are shown at their full recorded amount, including any unallocated portion, so the closing balance is the customer account balance. Recording a receipt is not bank settlement."}
