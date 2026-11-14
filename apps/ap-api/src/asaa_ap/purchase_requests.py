from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.procurement_models import PurchaseRequest, PurchaseRequestLine
from asaa_ap.procurement_schemas import PurchaseRequestCreate, PurchaseRequestRead, PurchaseRequestReview, PurchaseRequestSubmit
from asaa_ap.security import Principal, require_permission

router = APIRouter(prefix="/api/v1/ap/purchase-requests", tags=["Accounts Payable - Procurement"])
Db = Annotated[Session, Depends(get_db)]
CENT = Decimal("0.01")


def audit(db: Session, principal: Principal, action: str, row: PurchaseRequest, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id,
        actor_id=principal.subject,
        action=action,
        entity_type="purchase_request",
        entity_id=row.id,
        outcome="success",
        details=details,
        correlation_id=correlation_id,
    ))


def get_owned_request(db: Session, request_id: str, principal: Principal) -> PurchaseRequest:
    row = db.scalar(
        select(PurchaseRequest)
        .options(selectinload(PurchaseRequest.lines))
        .where(
            PurchaseRequest.id == request_id,
            PurchaseRequest.organization_id == principal.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    if row.requested_by != principal.subject and "procurement:request:read:all" not in principal.permissions:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return row


@router.post("", response_model=PurchaseRequestRead, status_code=201)
def create_purchase_request(
    payload: PurchaseRequestCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("procurement:request:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    total = sum((line.quantity * line.estimated_unit_cost for line in payload.lines), Decimal("0"))
    total = total.quantize(CENT, rounding=ROUND_HALF_UP)
    row = PurchaseRequest(
        organization_id=principal.organization_id,
        title=payload.title,
        purpose=payload.purpose,
        needed_by=payload.needed_by,
        currency=payload.currency,
        cost_center=payload.cost_center,
        project_reference=payload.project_reference,
        estimated_total=total,
        status="Draft",
        requested_by=principal.subject,
        created_by=principal.subject,
    )
    row.lines = [
        PurchaseRequestLine(
            description=line.description,
            quantity=line.quantity,
            unit_of_measure=line.unit_of_measure,
            estimated_unit_cost=line.estimated_unit_cost,
            estimated_line_total=(line.quantity * line.estimated_unit_cost).quantize(CENT, rounding=ROUND_HALF_UP),
        )
        for line in payload.lines
    ]
    db.add(row)
    try:
        db.flush()
        audit(db, principal, "purchase_request.created", row, {
            "currency": row.currency,
            "estimated_total": str(row.estimated_total),
            "line_count": len(row.lines),
            "status": row.status,
        }, x_correlation_id)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "purchase_request_conflict"}) from None


@router.get("", response_model=list[PurchaseRequestRead])
def list_purchase_requests(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("procurement:request:read"))],
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(PurchaseRequest).options(selectinload(PurchaseRequest.lines)).where(
        PurchaseRequest.organization_id == principal.organization_id
    )
    if "procurement:request:read:all" not in principal.permissions:
        stmt = stmt.where(PurchaseRequest.requested_by == principal.subject)
    if status:
        stmt = stmt.where(PurchaseRequest.status == status)
    return db.scalars(stmt.order_by(PurchaseRequest.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/{request_id}", response_model=PurchaseRequestRead)
def get_purchase_request(
    request_id: str,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("procurement:request:read"))],
):
    return get_owned_request(db, request_id, principal)


@router.post("/{request_id}/submit", response_model=PurchaseRequestRead)
def submit_purchase_request(
    request_id: str,
    payload: PurchaseRequestSubmit,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("procurement:request:submit"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    row = get_owned_request(db, request_id, principal)
    if row.requested_by != principal.subject:
        raise HTTPException(status_code=403, detail="Only the requester can submit this request")
    if row.status not in {"Draft", "Returned"}:
        raise HTTPException(status_code=409, detail="Only Draft or Returned requests can be submitted")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    row.status = "Submitted"
    row.submitted_at = datetime.now(timezone.utc)
    row.review_reason = payload.reason
    try:
        db.flush()
    except StaleDataError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "version_conflict"}) from None
    audit(db, principal, "purchase_request.submitted", row, {"version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{request_id}/review", response_model=PurchaseRequestRead)
def review_purchase_request(
    request_id: str,
    payload: PurchaseRequestReview,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("procurement:request:review"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    row = get_owned_request(db, request_id, principal)
    if row.requested_by == principal.subject:
        raise HTTPException(status_code=403, detail="Requester cannot review own purchase request")
    if row.status != "Submitted":
        raise HTTPException(status_code=409, detail="Only Submitted requests can be reviewed")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    row.status = {"approve": "Approved", "reject": "Rejected", "return": "Returned"}[payload.decision]
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewed_by = principal.subject
    row.review_reason = payload.reason
    try:
        db.flush()
    except StaleDataError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "version_conflict"}) from None
    audit(db, principal, "purchase_request.reviewed", row, {
        "decision": payload.decision,
        "status": row.status,
        "reason": payload.reason,
        "version": row.version,
    }, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row
