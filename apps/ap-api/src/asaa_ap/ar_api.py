from typing import Annotated
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import ARCustomer, ARReceipt, ARReceiptAllocation
from asaa_ap.schemas_ar import (
    ARCustomerCreate, ARCustomerRead, ARInvoiceCreate, ARInvoiceRead,
    ARInvoiceIssue, ARInvoiceUpdate, ARReceiptCreate, ARReceiptRead, ARReceiptReallocation,
)
from asaa_ap.security import Principal, require_permission
from asaa_ap.ar_service import (
    create_customer, create_invoice, create_receipt, get_customer,
    get_invoice, issue_invoice, list_invoices, money, update_draft_invoice, allocate_unapplied_receipt,
)

router = APIRouter(prefix="/api/v1/ar", tags=["Accounts Receivable"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/customers", response_model=ARCustomerRead, status_code=201)
def add_customer(payload: ARCustomerCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:customer:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return create_customer(db, payload, principal, x_correlation_id)


@router.get("/customers", response_model=list[ARCustomerRead])
def list_customers(db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:customer:read"))],
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ARCustomer).where(ARCustomer.organization_id == principal.organization_id)
    return db.scalars(stmt.order_by(ARCustomer.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/customers/{customer_id}", response_model=ARCustomerRead)
def customer_detail(customer_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:customer:read"))]):
    return get_customer(db, customer_id, principal.organization_id)


@router.post("/invoices", response_model=ARInvoiceRead, status_code=201)
def add_invoice(payload: ARInvoiceCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:invoice:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return create_invoice(db, payload, principal, x_correlation_id)


@router.get("/invoices", response_model=list[ARInvoiceRead])
def invoices(db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:invoice:read"))],
    status: str | None = None, customer_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    return list_invoices(db, principal, status, customer_id, limit, offset)


@router.get("/invoices/{invoice_id}", response_model=ARInvoiceRead)
def invoice_detail(invoice_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:invoice:read"))]):
    return get_invoice(db, invoice_id, principal)


@router.put("/invoices/{invoice_id}", response_model=ARInvoiceRead)
def update_invoice(invoice_id: str, payload: ARInvoiceUpdate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:invoice:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return update_draft_invoice(db, invoice_id, payload, principal, x_correlation_id)


@router.post("/invoices/{invoice_id}/issue", response_model=ARInvoiceRead)
def issue(invoice_id: str, payload: ARInvoiceIssue, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:invoice:issue"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return issue_invoice(db, invoice_id, payload.expected_version, payload.reason, principal, x_correlation_id)


@router.post("/receipts", response_model=ARReceiptRead, status_code=201)
def add_receipt(payload: ARReceiptCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:receipt:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return create_receipt(db, payload, principal, x_correlation_id)


@router.get("/receipts", response_model=list[ARReceiptRead])
def receipts(db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:receipt:read"))],
    customer_id: str | None = None, limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0)):
    stmt = select(ARReceipt).where(ARReceipt.organization_id == principal.organization_id)
    if customer_id:
        stmt = stmt.where(ARReceipt.customer_id == customer_id)
    rows = db.scalars(stmt.order_by(ARReceipt.created_at.desc()).offset(offset).limit(limit)).all()
    result = []
    for row in rows:
        applied = db.scalar(select(func.coalesce(func.sum(ARReceiptAllocation.amount), 0)).where(
            ARReceiptAllocation.receipt_id == row.id
        ))
        applied = money(applied or 0)
        result.append({
            "id": row.id, "organization_id": row.organization_id, "customer_id": row.customer_id,
            "currency": row.currency, "amount": row.amount, "received_date": row.received_date,
            "reference": row.reference, "method": row.method, "status": row.status,
            "applied_amount": applied, "unapplied_amount": money(row.amount - applied),
            "created_at": row.created_at, "created_by": row.created_by,
        })
    return result


@router.post("/receipts/{receipt_id}/allocations")
def reallocate_receipt(receipt_id: str, payload: ARReceiptReallocation, db: Db,
    principal: Annotated[Principal, Depends(require_permission("ar:receipt:allocate"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    return allocate_unapplied_receipt(
        db, receipt_id, payload.invoice_id, payload.amount, principal, x_correlation_id
    )
