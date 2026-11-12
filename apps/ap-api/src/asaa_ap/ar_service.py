from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from asaa_ap.models import AuditEvent, ARCustomer, ARInvoice, ARInvoiceLine, ARReceipt, ARReceiptAllocation
from asaa_ap.schemas_ar import ARCustomerCreate, ARInvoiceCreate, ARReceiptCreate
from asaa_ap.security import Principal


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def audit(db: Session, principal: Principal, action: str, entity_type: str, entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id,
    ))


def create_customer(db: Session, payload: ARCustomerCreate, principal: Principal, correlation_id: str | None):
    stmt = select(ARCustomer).where(ARCustomer.organization_id == principal.organization_id)
    rows = db.scalars(stmt).all()
    normalized = " ".join(payload.legal_name.casefold().split())
    for row in rows:
        if " ".join(row.legal_name.casefold().split()) == normalized or (
            payload.email and row.email and payload.email.casefold() == row.email.casefold()
        ):
            raise HTTPException(status_code=409, detail={"code": "possible_duplicate_customer", "customer_id": row.id})
    row = ARCustomer(
        organization_id=principal.organization_id, customer_code=payload.customer_code,
        legal_name=payload.legal_name, trading_name=payload.trading_name, email=payload.email,
        phone=payload.phone, billing_address=payload.billing_address,
        status="Active", created_by=principal.subject,
    )
    db.add(row)
    try:
        db.flush()
        audit(db, principal, "customer.created", "customer", row.id, {"status": row.status}, correlation_id)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "customer_code_conflict"}) from None


def get_customer(db: Session, customer_id: str, organization_id: str):
    row = db.scalar(select(ARCustomer).where(
        ARCustomer.id == customer_id, ARCustomer.organization_id == organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


def amount_paid(db: Session, invoice_id: str) -> Decimal:
    value = db.scalar(select(func.coalesce(func.sum(ARReceiptAllocation.amount), 0)).join(
        ARReceipt, ARReceipt.id == ARReceiptAllocation.receipt_id
    ).where(
        ARReceiptAllocation.invoice_id == invoice_id, ARReceipt.status == "Recorded"
    ))
    return money(Decimal(value or 0))


def invoice_view(db: Session, invoice: ARInvoice) -> dict:
    paid = amount_paid(db, invoice.id)
    lines = db.scalars(select(ARInvoiceLine).where(ARInvoiceLine.invoice_id == invoice.id)).all()
    return {
        "id": invoice.id, "organization_id": invoice.organization_id, "customer_id": invoice.customer_id,
        "invoice_number": invoice.invoice_number, "currency": invoice.currency,
        "issue_date": invoice.issue_date, "due_date": invoice.due_date, "status": invoice.status,
        "subtotal": invoice.subtotal, "tax_total": invoice.tax_total, "total": invoice.total,
        "amount_paid": paid, "outstanding": money(invoice.total - paid), "notes": invoice.notes,
        "version": invoice.version, "created_at": invoice.created_at, "created_by": invoice.created_by,
        "lines": lines,
    }


def create_invoice(db: Session, payload: ARInvoiceCreate, principal: Principal, correlation_id: str | None):
    customer = get_customer(db, payload.customer_id, principal.organization_id)
    if customer.status != "Active":
        raise HTTPException(status_code=409, detail="Customer account is not active")
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    line_rows = []
    for item in payload.lines:
        net = money(item.quantity * item.unit_price)
        tax = money(item.tax_amount)
        subtotal += net
        tax_total += tax
        line_rows.append((item, net + tax))
    subtotal, tax_total = money(subtotal), money(tax_total)
    total = money(subtotal + tax_total)
    row = ARInvoice(
        organization_id=principal.organization_id, customer_id=customer.id,
        invoice_number=payload.invoice_number, currency=payload.currency,
        issue_date=payload.issue_date, due_date=payload.due_date, status="Draft",
        subtotal=subtotal, tax_total=tax_total, total=total, notes=payload.notes,
        created_by=principal.subject,
    )
    db.add(row)
    try:
        db.flush()
        for item, line_total in line_rows:
            db.add(ARInvoiceLine(
                invoice_id=row.id, description=item.description, quantity=item.quantity,
                unit_price=item.unit_price, tax_amount=money(item.tax_amount), line_total=line_total,
            ))
        audit(db, principal, "invoice.created", "ar_invoice", row.id, {
            "customer_id": customer.id, "currency": row.currency, "total": str(total), "status": "Draft"
        }, correlation_id)
        db.commit()
        db.refresh(row)
        return invoice_view(db, row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "invoice_number_conflict"}) from None


def list_invoices(db: Session, principal: Principal, status: str | None, customer_id: str | None, limit: int, offset: int):
    stmt = select(ARInvoice).where(ARInvoice.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(ARInvoice.status == status)
    if customer_id:
        stmt = stmt.where(ARInvoice.customer_id == customer_id)
    rows = db.scalars(stmt.order_by(ARInvoice.created_at.desc()).offset(offset).limit(limit)).all()
    return [invoice_view(db, row) for row in rows]


def get_invoice(db: Session, invoice_id: str, principal: Principal):
    row = db.scalar(select(ARInvoice).where(
        ARInvoice.id == invoice_id, ARInvoice.organization_id == principal.organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_view(db, row)


def issue_invoice(db: Session, invoice_id: str, expected_version: int, reason: str, principal: Principal, correlation_id: str | None):
    row = db.scalar(select(ARInvoice).where(
        ARInvoice.id == invoice_id, ARInvoice.organization_id == principal.organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if row.version != expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    if row.status != "Draft":
        raise HTTPException(status_code=409, detail={"code": "invoice_not_draft"})
    row.status = "Issued"
    try:
        db.flush()
    except (StaleDataError, IntegrityError):
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "invoice_issue_conflict"}) from None
    audit(db, principal, "invoice.issued", "ar_invoice", row.id, {"reason": reason, "total": str(row.total)}, correlation_id)
    db.commit()
    db.refresh(row)
    return invoice_view(db, row)


def create_receipt(db: Session, payload: ARReceiptCreate, principal: Principal, correlation_id: str | None):
    customer = get_customer(db, payload.customer_id, principal.organization_id)
    if customer.status != "Active":
        raise HTTPException(status_code=409, detail="Customer account is not active")
    receipt = ARReceipt(
        organization_id=principal.organization_id, customer_id=customer.id,
        currency=payload.currency, amount=money(payload.amount), received_date=payload.received_date,
        reference=payload.reference, method=payload.method, status="Recorded", created_by=principal.subject,
    )
    db.add(receipt)
    try:
        db.flush()
        applied = Decimal("0")
        for allocation in payload.allocations:
            invoice = db.scalar(select(ARInvoice).where(
                ARInvoice.id == allocation.invoice_id,
                ARInvoice.organization_id == principal.organization_id,
                ARInvoice.customer_id == customer.id,
            ).with_for_update())
            if not invoice:
                raise HTTPException(status_code=404, detail={"code": "invoice_not_found", "invoice_id": allocation.invoice_id})
            if invoice.currency != payload.currency:
                raise HTTPException(status_code=409, detail={"code": "currency_mismatch"})
            if invoice.status not in {"Issued", "Partially Paid"}:
                raise HTTPException(status_code=409, detail={"code": "invoice_not_receivable", "invoice_id": invoice.id})
            already_paid = amount_paid(db, invoice.id)
            if money(allocation.amount) > money(invoice.total - already_paid):
                raise HTTPException(status_code=409, detail={"code": "allocation_exceeds_outstanding", "invoice_id": invoice.id})
            db.add(ARReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id, amount=money(allocation.amount)))
            applied += money(allocation.amount)
            db.flush()
            if money(already_paid + allocation.amount) == money(invoice.total):
                invoice.status = "Paid"
            else:
                invoice.status = "Partially Paid"
        audit(db, principal, "receipt.recorded", "ar_receipt", receipt.id, {
            "customer_id": customer.id, "currency": receipt.currency, "amount": str(receipt.amount),
            "applied_amount": str(money(applied)), "unapplied_amount": str(money(receipt.amount - applied)),
        }, correlation_id)
        db.commit()
        db.refresh(receipt)
        return {
            "id": receipt.id, "organization_id": receipt.organization_id, "customer_id": receipt.customer_id,
            "currency": receipt.currency, "amount": receipt.amount, "received_date": receipt.received_date,
            "reference": receipt.reference, "method": receipt.method, "status": receipt.status,
            "applied_amount": money(applied), "unapplied_amount": money(receipt.amount - applied),
            "created_at": receipt.created_at, "created_by": receipt.created_by,
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "receipt_allocation_conflict"}) from None
