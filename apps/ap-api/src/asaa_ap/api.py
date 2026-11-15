from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent, Supplier
from asaa_ap.schemas import SupplierCreate, SupplierRead, SupplierUpdate, StatusChange, AuditRead
from asaa_ap.security import Principal, get_principal, require_permission
from asaa_ap.service import create_supplier, update_supplier, change_supplier_status, find_duplicates

router = APIRouter(prefix="/api/v1/ap", tags=["Accounts Payable"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/suppliers", response_model=SupplierRead, status_code=201)
def create(payload: SupplierCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:write"))], x_correlation_id: Annotated[str | None, Header()] = None):
    return create_supplier(db, payload, principal, x_correlation_id)


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:read"))], status: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(Supplier).where(Supplier.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(Supplier.status == status)
    return db.scalars(stmt.order_by(Supplier.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/suppliers/duplicates")
def duplicates(db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:read"))], legal_name: str = Query(min_length=2), email: str | None = None, registration_reference: str | None = None):
    return find_duplicates(db, principal.organization_id, legal_name, email, registration_reference)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:read"))]):
    row = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update(supplier_id: str, payload: SupplierUpdate, db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:write"))], x_correlation_id: Annotated[str | None, Header()] = None):
    return update_supplier(db, supplier_id, payload, principal, x_correlation_id)


@router.post("/suppliers/{supplier_id}/status", response_model=SupplierRead)
def change_status(supplier_id: str, payload: StatusChange, db: Db, principal: Annotated[Principal, Depends(require_permission("supplier:status"))], x_correlation_id: Annotated[str | None, Header()] = None):
    return change_supplier_status(db, supplier_id, payload, principal, x_correlation_id)


@router.get("/audit-events", response_model=list[AuditRead])
def list_audit(db: Db, principal: Annotated[Principal, Depends(require_permission("audit:read"))], limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
               action: str | None = Query(default=None, max_length=100, description="action prefix, e.g. supplier."), entity_type: str | None = Query(default=None, max_length=100),
               actor_id: str | None = Query(default=None, max_length=128), outcome: str | None = Query(default=None, pattern="^(success|failure)$")):
    stmt = select(AuditEvent).where(AuditEvent.organization_id == principal.organization_id)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action, autoescape=True))
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()
