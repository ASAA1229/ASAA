"""Procurement-to-payment: purchase orders, goods receipts, supplier invoices (three-way match), payment batches and payables ageing.

Maker-checker is enforced at every approval step (the approver can never be the maker). Recording a payment batch as paid records
that the payment was made outside this system; no bank or payment-provider instruction is generated. Match tolerance is a
configuration value (ASAA_AP_AP_MATCH_TOLERANCE_AMOUNT, default exact match) pending owner policy. No tax or accounting rules are applied.
"""
import secrets
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from asaa_ap.config import get_settings
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent, Supplier
from asaa_ap.procurement_models import PurchaseRequest
from asaa_ap.security import Principal, require_permission
from asaa_integration.emitter import emit_for_audit
from asaa_payables.models import (GoodsReceipt, GoodsReceiptLine, PaymentBatch, PaymentBatchItem, PurchaseOrder, PurchaseOrderLine,
                                  SupplierInvoice)
from asaa_payables.schemas import (BatchCreate, BatchOut, BatchPaid, Decision, InvoiceCreate, InvoiceOut, POCreate, POOut, Reason,
                                   ReceiptCreate, ReceiptOut)

router = APIRouter(prefix="/api/v1/ap", tags=["Accounts Payable - Purchase to Pay"])
Db = Annotated[Session, Depends(get_db)]
Corr = Annotated[str | None, Header()]
CENT = Decimal("0.01")
AGING_BUCKETS = (("current", None, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, None))


def money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def audit(db: Session, principal: Principal, action: str, kind: str, entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=kind,
                      entity_id=entity_id, details=details, correlation_id=correlation_id))
    emit_for_audit(db, principal.organization_id, principal.subject, action, entity_id, details, correlation_id)


def now() -> datetime:
    return datetime.now(timezone.utc)


def fetch(db: Session, model, row_id: str, org: str, label: str, *options):
    stmt = select(model).where(model.id == row_id, model.organization_id == org)
    if options:
        stmt = stmt.options(*options)
    row = db.scalar(stmt.with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def active_supplier(db: Session, supplier_id: str, org: str) -> Supplier:
    supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == org))
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if supplier.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "supplier_not_active", "status": supplier.status})
    return supplier


def commit(db: Session, conflict_code: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": conflict_code}) from None


# ---- purchase orders -------------------------------------------------------------------------------------------------------

@router.post("/purchase-orders", response_model=POOut, status_code=201)
def create_po(payload: POCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:write"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    active_supplier(db, payload.supplier_id, org)
    if payload.purchase_request_id:
        pr = db.scalar(select(PurchaseRequest).where(PurchaseRequest.id == payload.purchase_request_id, PurchaseRequest.organization_id == org))
        if not pr or pr.status != "Approved":
            raise HTTPException(status_code=409, detail={"code": "purchase_request_not_approved"})
        if pr.currency != payload.currency:
            raise HTTPException(status_code=409, detail={"code": "currency_mismatch"})
    lines = [PurchaseOrderLine(description=l.description, quantity=l.quantity, unit_of_measure=l.unit_of_measure, unit_price=l.unit_price,
                               line_total=money(l.quantity * l.unit_price), received_quantity=Decimal("0")) for l in payload.lines]
    row = PurchaseOrder(organization_id=org, po_number=f"PO-{date.today():%Y%m%d}-{secrets.token_hex(3).upper()}", supplier_id=payload.supplier_id,
                        purchase_request_id=payload.purchase_request_id, currency=payload.currency, notes=payload.notes, status="Draft",
                        total=sum((l.line_total for l in lines), Decimal("0")), created_by=principal.subject, lines=lines)
    db.add(row)
    db.flush()
    audit(db, principal, "purchase_order.created", "purchase_order", row.id, {"total": str(row.total), "currency": row.currency, "po_number": row.po_number}, x_correlation_id)
    commit(db, "purchase_order_conflict")
    db.refresh(row)
    return row


@router.get("/purchase-orders", response_model=list[POOut])
def list_pos(db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:read"))], status: str | None = None,
             supplier_id: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    return db.scalars(stmt.order_by(PurchaseOrder.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/purchase-orders/{po_id}", response_model=POOut)
def get_po(po_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:read"))]):
    return fetch(db, PurchaseOrder, po_id, principal.organization_id, "Purchase order", selectinload(PurchaseOrder.lines))


@router.post("/purchase-orders/{po_id}/review", response_model=POOut)
def review_po(po_id: str, payload: Decision, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:review"))], x_correlation_id: Corr = None):
    row = fetch(db, PurchaseOrder, po_id, principal.organization_id, "Purchase order", selectinload(PurchaseOrder.lines))
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a purchase order cannot review it")
    if row.status != "Draft":
        raise HTTPException(status_code=409, detail="Only Draft purchase orders can be reviewed")
    row.status = "Approved" if payload.decision == "approve" else "Rejected"
    row.reviewed_by, row.reviewed_at, row.review_reason = principal.subject, now(), payload.reason
    audit(db, principal, "purchase_order.reviewed", "purchase_order", row.id, {"decision": payload.decision, "reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/purchase-orders/{po_id}/issue", response_model=POOut)
def issue_po(po_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:issue"))], x_correlation_id: Corr = None):
    row = fetch(db, PurchaseOrder, po_id, principal.organization_id, "Purchase order", selectinload(PurchaseOrder.lines))
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail="Only Approved purchase orders can be issued")
    active_supplier(db, row.supplier_id, principal.organization_id)
    row.status, row.issued_at = "Issued", now()
    audit(db, principal, "purchase_order.issued", "purchase_order", row.id, {"po_number": row.po_number}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/purchase-orders/{po_id}/cancel", response_model=POOut)
def cancel_po(po_id: str, payload: Reason, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:po:write"))], x_correlation_id: Corr = None):
    row = fetch(db, PurchaseOrder, po_id, principal.organization_id, "Purchase order", selectinload(PurchaseOrder.lines))
    if row.status not in {"Draft", "Approved", "Issued"}:
        raise HTTPException(status_code=409, detail="Purchase order cannot be cancelled in its current status")
    if any(l.received_quantity > 0 for l in row.lines):
        raise HTTPException(status_code=409, detail={"code": "goods_already_received"})
    if db.scalar(select(SupplierInvoice.id).where(SupplierInvoice.purchase_order_id == row.id, SupplierInvoice.status != "Rejected").limit(1)):
        raise HTTPException(status_code=409, detail={"code": "invoices_reference_purchase_order"})
    row.status = "Cancelled"
    audit(db, principal, "purchase_order.cancelled", "purchase_order", row.id, {"reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


# ---- goods receipts ------------------------------------------------------------------------------------------------------

@router.post("/goods-receipts", response_model=ReceiptOut, status_code=201)
def create_receipt(payload: ReceiptCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:receipt:write"))], x_correlation_id: Corr = None):
    po = fetch(db, PurchaseOrder, payload.purchase_order_id, principal.organization_id, "Purchase order", selectinload(PurchaseOrder.lines))
    if po.status != "Issued":
        raise HTTPException(status_code=409, detail="Goods can only be received against an Issued purchase order")
    by_id = {l.id: l for l in po.lines}
    totals: dict[str, Decimal] = {}
    for line in payload.lines:
        if line.po_line_id not in by_id:
            raise HTTPException(status_code=422, detail={"code": "unknown_po_line", "po_line_id": line.po_line_id})
        totals[line.po_line_id] = totals.get(line.po_line_id, Decimal("0")) + line.quantity
    for line_id, qty in totals.items():
        po_line = by_id[line_id]
        if po_line.received_quantity + qty > po_line.quantity:
            raise HTTPException(status_code=409, detail={"code": "receipt_exceeds_ordered", "po_line_id": line_id,
                                                         "remaining": str(po_line.quantity - po_line.received_quantity)})
    for line_id, qty in totals.items():
        by_id[line_id].received_quantity += qty
    row = GoodsReceipt(organization_id=principal.organization_id, purchase_order_id=po.id, received_date=payload.received_date, reference=payload.reference,
                       notes=payload.notes, received_by=principal.subject,
                       lines=[GoodsReceiptLine(po_line_id=l.po_line_id, quantity=l.quantity) for l in payload.lines])
    db.add(row)
    db.flush()
    audit(db, principal, "goods_receipt.recorded", "goods_receipt", row.id, {"purchase_order_id": po.id, "line_count": len(row.lines)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/goods-receipts", response_model=list[ReceiptOut])
def list_receipts(db: Db, principal: Annotated[Principal, Depends(require_permission("ap:receipt:read"))], purchase_order_id: str | None = None,
                  limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).where(GoodsReceipt.organization_id == principal.organization_id)
    if purchase_order_id:
        stmt = stmt.where(GoodsReceipt.purchase_order_id == purchase_order_id)
    return db.scalars(stmt.order_by(GoodsReceipt.created_at.desc()).offset(offset).limit(limit)).all()


# ---- supplier invoices ---------------------------------------------------------------------------------------------------

@router.post("/supplier-invoices", response_model=InvoiceOut, status_code=201)
def capture_invoice(payload: InvoiceCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:write"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    supplier = db.scalar(select(Supplier).where(Supplier.id == payload.supplier_id, Supplier.organization_id == org))
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if supplier.status in {"Draft", "Archived"}:
        raise HTTPException(status_code=409, detail={"code": "supplier_not_usable", "status": supplier.status})
    if payload.due_date < payload.invoice_date:
        raise HTTPException(status_code=422, detail={"code": "due_before_invoice_date"})
    if payload.tax_total >= payload.total:
        raise HTTPException(status_code=422, detail={"code": "tax_not_less_than_total"})
    if payload.purchase_order_id:
        po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.organization_id == org))
        if not po or po.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=404, detail="Purchase order not found for this supplier")
        if po.currency != payload.currency:
            raise HTTPException(status_code=409, detail={"code": "currency_mismatch"})
    row = SupplierInvoice(organization_id=org, supplier_id=payload.supplier_id, purchase_order_id=payload.purchase_order_id, invoice_number=payload.invoice_number,
                          currency=payload.currency, invoice_date=payload.invoice_date, due_date=payload.due_date, tax_total=payload.tax_total, total=payload.total,
                          status="Captured", captured_by=principal.subject)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "duplicate_supplier_invoice"}) from None
    audit(db, principal, "supplier_invoice.captured", "supplier_invoice", row.id, {"supplier_id": row.supplier_id, "total": str(row.total), "currency": row.currency}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/supplier-invoices", response_model=list[InvoiceOut])
def list_invoices(db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:read"))], status: str | None = None, supplier_id: str | None = None,
                  limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(SupplierInvoice).where(SupplierInvoice.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(SupplierInvoice.status == status)
    if supplier_id:
        stmt = stmt.where(SupplierInvoice.supplier_id == supplier_id)
    return db.scalars(stmt.order_by(SupplierInvoice.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/supplier-invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:read"))]):
    return fetch(db, SupplierInvoice, invoice_id, principal.organization_id, "Supplier invoice")


def evaluate_match(db: Session, invoice: SupplierInvoice) -> dict:
    tolerance = get_settings().ap_match_tolerance_amount
    reasons: list[str] = []
    result: dict = {"checked_at": now().isoformat(), "tolerance": str(tolerance)}
    net = money(invoice.total - invoice.tax_total)
    result["invoice_net"] = str(net)
    if not invoice.purchase_order_id:
        reasons.append("no_purchase_order")
    else:
        po = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.id == invoice.purchase_order_id))
        if po.status not in {"Issued", "Closed"}:
            reasons.append("purchase_order_not_issued")
        received_value = money(sum((l.received_quantity * l.unit_price for l in po.lines), Decimal("0")))
        invoiced_elsewhere = db.scalars(select(SupplierInvoice).where(
            SupplierInvoice.purchase_order_id == po.id, SupplierInvoice.id != invoice.id, SupplierInvoice.status.notin_(["Rejected", "Captured", "Exception"]))).all()
        already = money(sum((i.total - i.tax_total for i in invoiced_elsewhere), Decimal("0")))
        result.update({"received_value": str(received_value), "already_invoiced_net": str(already), "ordered_value": str(po.total)})
        if received_value == 0:
            reasons.append("nothing_received")
        if net > money(received_value - already) + tolerance:
            reasons.append("invoice_exceeds_received_value")
        if net > po.total + tolerance:
            reasons.append("invoice_exceeds_order_value")
    result["exceptions"] = reasons
    result["outcome"] = "Matched" if not reasons else "Exception"
    return result


@router.post("/supplier-invoices/{invoice_id}/match", response_model=InvoiceOut)
def match_invoice(invoice_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:match"))], x_correlation_id: Corr = None):
    row = fetch(db, SupplierInvoice, invoice_id, principal.organization_id, "Supplier invoice")
    if row.status not in {"Captured", "Exception", "Matched"}:
        raise HTTPException(status_code=409, detail="Invoice is no longer eligible for matching")
    result = evaluate_match(db, row)
    row.match_result, row.status = result, result["outcome"]
    audit(db, principal, "supplier_invoice.matched", "supplier_invoice", row.id, {"outcome": result["outcome"], "exceptions": result["exceptions"]}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/supplier-invoices/{invoice_id}/review", response_model=InvoiceOut)
def review_invoice(invoice_id: str, payload: Decision, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:review"))], x_correlation_id: Corr = None):
    row = fetch(db, SupplierInvoice, invoice_id, principal.organization_id, "Supplier invoice")
    if row.captured_by == principal.subject:
        raise HTTPException(status_code=403, detail="The person who captured an invoice cannot approve it")
    if row.status not in {"Matched", "Exception"}:
        raise HTTPException(status_code=409, detail="Only Matched or Exception invoices can be reviewed (run matching first)")
    if payload.decision == "approve" and row.status == "Exception" and "ap:invoice:approve_exception" not in principal.permissions:
        raise HTTPException(status_code=403, detail="Approving a match exception requires ap:invoice:approve_exception")
    exception_override = row.status == "Exception" and payload.decision == "approve"
    row.status = "Approved" if payload.decision == "approve" else "Rejected"
    row.reviewed_by, row.reviewed_at, row.review_reason = principal.subject, now(), payload.reason
    audit(db, principal, "supplier_invoice.reviewed", "supplier_invoice", row.id, {"decision": payload.decision, "reason": payload.reason, "exception_override": exception_override}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


# ---- payment batches -------------------------------------------------------------------------------------------------------

def batch_with_items(db: Session, batch_id: str, org: str) -> PaymentBatch:
    return fetch(db, PaymentBatch, batch_id, org, "Payment batch", selectinload(PaymentBatch.items))


@router.post("/payment-batches", response_model=BatchOut, status_code=201)
def create_batch(payload: BatchCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:payment:write"))], x_correlation_id: Corr = None):
    ids = list(dict.fromkeys(payload.invoice_ids))
    invoices = db.scalars(select(SupplierInvoice).where(SupplierInvoice.organization_id == principal.organization_id, SupplierInvoice.id.in_(ids)).with_for_update()).all()
    if len(invoices) != len(ids):
        raise HTTPException(status_code=404, detail="One or more supplier invoices were not found")
    if any(i.status != "Approved" for i in invoices):
        raise HTTPException(status_code=409, detail={"code": "invoice_not_payable", "invoice_ids": [i.id for i in invoices if i.status != "Approved"]})
    if len({i.currency for i in invoices}) != 1:
        raise HTTPException(status_code=409, detail={"code": "mixed_currencies"})
    batch = PaymentBatch(organization_id=principal.organization_id, currency=invoices[0].currency, status="Draft", created_by=principal.subject,
                         total=sum((i.total for i in invoices), Decimal("0")), items=[PaymentBatchItem(invoice_id=i.id, amount=i.total) for i in invoices])
    for invoice in invoices:
        invoice.status = "In Payment Batch"
    db.add(batch)
    db.flush()
    audit(db, principal, "payment_batch.created", "payment_batch", batch.id, {"total": str(batch.total), "currency": batch.currency, "invoice_count": len(invoices)}, x_correlation_id)
    commit(db, "payment_batch_conflict")
    db.refresh(batch)
    return batch


@router.get("/payment-batches", response_model=list[BatchOut])
def list_batches(db: Db, principal: Annotated[Principal, Depends(require_permission("ap:payment:read"))], status: str | None = None,
                 limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(PaymentBatch).options(selectinload(PaymentBatch.items)).where(PaymentBatch.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(PaymentBatch.status == status)
    return db.scalars(stmt.order_by(PaymentBatch.created_at.desc()).offset(offset).limit(limit)).all()


@router.post("/payment-batches/{batch_id}/approve", response_model=BatchOut)
def approve_batch(batch_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:payment:approve"))], x_correlation_id: Corr = None):
    batch = batch_with_items(db, batch_id, principal.organization_id)
    if batch.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a payment batch cannot approve it")
    if batch.status != "Draft":
        raise HTTPException(status_code=409, detail="Only Draft payment batches can be approved")
    batch.status, batch.approved_by, batch.approved_at = "Approved", principal.subject, now()
    audit(db, principal, "payment_batch.approved", "payment_batch", batch.id, {"total": str(batch.total)}, x_correlation_id)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/payment-batches/{batch_id}/cancel", response_model=BatchOut)
def cancel_batch(batch_id: str, payload: Reason, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:payment:write"))], x_correlation_id: Corr = None):
    batch = batch_with_items(db, batch_id, principal.organization_id)
    if batch.status not in {"Draft", "Approved"}:
        raise HTTPException(status_code=409, detail="Only Draft or Approved payment batches can be cancelled")
    for item in batch.items:
        invoice = db.get(SupplierInvoice, item.invoice_id)
        invoice.status = "Approved"
    batch.items.clear()
    batch.status = "Cancelled"
    audit(db, principal, "payment_batch.cancelled", "payment_batch", batch.id, {"reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/payment-batches/{batch_id}/record-payment", response_model=BatchOut)
def record_payment(batch_id: str, payload: BatchPaid, db: Db, principal: Annotated[Principal, Depends(require_permission("ap:payment:record"))], x_correlation_id: Corr = None):
    batch = batch_with_items(db, batch_id, principal.organization_id)
    if batch.status != "Approved":
        raise HTTPException(status_code=409, detail="Only Approved payment batches can be recorded as paid")
    if principal.subject in {batch.created_by, batch.approved_by}:
        raise HTTPException(status_code=403, detail="The maker or approver of a payment batch cannot record its payment")
    stamp = now()
    for item in batch.items:
        invoice = db.get(SupplierInvoice, item.invoice_id)
        invoice.status, invoice.paid_at = "Paid", stamp
    batch.status, batch.paid_by, batch.paid_at, batch.payment_reference = "Paid", principal.subject, stamp, payload.payment_reference
    audit(db, principal, "payment_batch.payment_recorded", "payment_batch", batch.id, {"payment_reference": payload.payment_reference, "total": str(batch.total)}, x_correlation_id)
    db.commit()
    db.refresh(batch)
    return batch


# ---- payables ageing ----------------------------------------------------------------------------------------------------

@router.get("/aging")
def payables_aging(db: Db, principal: Annotated[Principal, Depends(require_permission("ap:invoice:read"))], as_of: date | None = None):
    """Unpaid approved-or-in-flight supplier invoices bucketed by days past due, per currency (never converted across currencies)."""
    as_of = as_of or date.today()
    rows = db.scalars(select(SupplierInvoice).where(SupplierInvoice.organization_id == principal.organization_id,
                                                     SupplierInvoice.status.in_(["Approved", "In Payment Batch"]))).all()
    out: dict[str, dict] = {}
    for inv in rows:
        days = (as_of - inv.due_date).days
        label = next(name for name, lo, hi in AGING_BUCKETS if (lo is None or days >= lo) and (hi is None or days <= hi))
        bucket = out.setdefault(inv.currency, {name: "0.00" for name, _, _ in AGING_BUCKETS} | {"total": "0.00", "invoice_count": 0})
        bucket[label] = str(money(Decimal(bucket[label]) + inv.total))
        bucket["total"] = str(money(Decimal(bucket["total"]) + inv.total))
        bucket["invoice_count"] += 1
    return {"as_of": as_of.isoformat(), "generated_at": now().isoformat(), "sources": ["ap_supplier_invoices"], "by_currency": out,
            "note": "Invoices awaiting match or approval are excluded. Bucket boundaries are a reporting convention, not a payment-terms rule."}
