"""Service catalogue, client engagements (SOW milestones, delivery and client acceptance) and work orders.

Independent-review rules: a service is activated by someone other than its maker; an engagement is activated by someone other than its
creator; a milestone is accepted by someone other than the person who marked it delivered; a work order is verified by someone other
than the person who completed it. Accepted billable milestones can be linked to a receivables invoice for the same customer; this
module never creates invoices or applies pricing, tax or commercial terms.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import ARCustomer, ARInvoice, AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_delivery.models import Engagement, Milestone, ServiceDefinition, WorkOrder
from asaa_people.models import Employee

router = APIRouter(prefix="/api/v1/delivery", tags=["Service Delivery"])
Db = Annotated[Session, Depends(get_db)]
Corr = Annotated[str | None, Header()]
CODE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$"
ENGAGEMENT_TRANSITIONS = {"Draft": {"Active", "Cancelled"}, "Active": {"On Hold", "Completed", "Cancelled"}, "On Hold": {"Active", "Cancelled"}, "Completed": set(), "Cancelled": set()}


def now() -> datetime:
    return datetime.now(timezone.utc)


def audit(db: Session, principal: Principal, action: str, kind: str, entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=kind, entity_id=entity_id, details=details, correlation_id=correlation_id))


def owned(db: Session, model, row_id: str, org: str, label: str, lock: bool = True):
    stmt = select(model).where(model.id == row_id, model.organization_id == org)
    row = db.scalar(stmt.with_for_update() if lock else stmt)
    if not row:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


def flush_unique(db: Session, code: str):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": code}) from None


class ServiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    owner_subject: str | None = Field(default=None, max_length=128)
    service_tier: str | None = Field(default=None, max_length=60)


class EngagementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=CODE)
    title: str = Field(min_length=3, max_length=200)
    customer_id: str = Field(min_length=1, max_length=36)
    service_id: str | None = Field(default=None, max_length=36)
    sow_reference: str | None = Field(default=None, max_length=160)
    project_reference: str | None = Field(default=None, max_length=160)
    owner_subject: str | None = Field(default=None, max_length=128)
    start_date: date
    end_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def upper(cls, value):
        return value.upper() if value else value

    @model_validator(mode="after")
    def coherent(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if self.budget_amount is not None and not self.currency:
            raise ValueError("currency is required with a budget amount")
        return self


class MilestoneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    deliverable: str | None = Field(default=None, max_length=1000)
    due_date: date
    billable_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Active", "On Hold", "Completed", "Cancelled"]
    reason: str = Field(min_length=3, max_length=500)


class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: str = Field(min_length=3, max_length=1000)


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accept", "reject"]
    client_acceptance_reference: str = Field(min_length=3, max_length=300)


class LinkInvoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str = Field(min_length=1, max_length=36)


class WorkOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engagement_id: str | None = Field(default=None, max_length=36)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: Literal["Low", "Normal", "High", "Urgent"] = "Normal"
    due_date: date | None = None


class AssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=36)


def iso(value):
    return value.isoformat() if value else None


def dump_service(s: ServiceDefinition) -> dict:
    return {"id": s.id, "code": s.code, "name": s.name, "description": s.description, "owner_subject": s.owner_subject, "service_tier": s.service_tier, "status": s.status,
            "created_by": s.created_by, "reviewed_by": s.reviewed_by, "review_reason": s.review_reason}


def dump_milestone(m: Milestone) -> dict:
    return {"id": m.id, "engagement_id": m.engagement_id, "title": m.title, "deliverable": m.deliverable, "due_date": iso(m.due_date), "billable_amount": str(m.billable_amount) if m.billable_amount is not None else None,
            "status": m.status, "delivered_by": m.delivered_by, "delivered_at": iso(m.delivered_at), "delivery_evidence": m.delivery_evidence, "accepted_by": m.accepted_by,
            "accepted_at": iso(m.accepted_at), "client_acceptance_reference": m.client_acceptance_reference, "invoice_id": m.invoice_id}


def dump_engagement(e: Engagement, milestones: list[Milestone] | None = None) -> dict:
    out = {"id": e.id, "code": e.code, "title": e.title, "customer_id": e.customer_id, "service_id": e.service_id, "sow_reference": e.sow_reference, "project_reference": e.project_reference,
           "owner_subject": e.owner_subject, "start_date": iso(e.start_date), "end_date": iso(e.end_date), "currency": e.currency,
           "budget_amount": str(e.budget_amount) if e.budget_amount is not None else None, "status": e.status, "created_by": e.created_by}
    if milestones is not None:
        today = date.today()
        out["milestones"] = [dump_milestone(m) for m in milestones]
        out["progress"] = {"milestones": len(milestones), "accepted": sum(m.status == "Accepted" for m in milestones),
                           "overdue": sum(m.status in {"Planned", "In Progress"} and m.due_date < today for m in milestones),
                           "billable_accepted_not_invoiced": str(sum((m.billable_amount or Decimal("0") for m in milestones if m.status == "Accepted" and not m.invoice_id), Decimal("0")))}
    return out


def dump_work_order(w: WorkOrder) -> dict:
    return {"id": w.id, "engagement_id": w.engagement_id, "title": w.title, "description": w.description, "priority": w.priority, "due_date": iso(w.due_date),
            "assignee_employee_id": w.assignee_employee_id, "status": w.status, "completion_evidence": w.completion_evidence, "completed_by": w.completed_by,
            "verified_by": w.verified_by, "created_by": w.created_by}


# ---- services ---------------------------------------------------------------------------------------------------------

@router.post("/services", status_code=201)
def create_service(payload: ServiceIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:service:write"))], x_correlation_id: Corr = None):
    row = ServiceDefinition(organization_id=principal.organization_id, created_by=principal.subject, status="Draft", **payload.model_dump())
    db.add(row)
    flush_unique(db, "service_code_exists")
    audit(db, principal, "service.created", "dlv_service", row.id, {"code": row.code}, x_correlation_id)
    db.commit()
    return dump_service(row)


@router.get("/services")
def list_services(db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:service:read"))], status: str | None = None):
    stmt = select(ServiceDefinition).where(ServiceDefinition.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(ServiceDefinition.status == status)
    return [dump_service(s) for s in db.scalars(stmt.order_by(ServiceDefinition.code)).all()]


@router.post("/services/{service_id}/review")
def review_service(service_id: str, payload: ReviewIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:service:approve"))], x_correlation_id: Corr = None):
    row = owned(db, ServiceDefinition, service_id, principal.organization_id, "Service")
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail="The maker of a service cannot approve it")
    if row.status != "Draft":
        raise HTTPException(status_code=409, detail="Only Draft services can be reviewed")
    row.status = "Active" if payload.decision == "approve" else "Rejected"
    row.reviewed_by, row.review_reason = principal.subject, payload.reason
    audit(db, principal, "service.reviewed", "dlv_service", row.id, {"decision": payload.decision, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return dump_service(row)


@router.post("/services/{service_id}/retire")
def retire_service(service_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:service:write"))], x_correlation_id: Corr = None):
    row = owned(db, ServiceDefinition, service_id, principal.organization_id, "Service")
    if row.status != "Active":
        raise HTTPException(status_code=409, detail="Only Active services can be retired")
    row.status = "Retired"
    audit(db, principal, "service.retired", "dlv_service", row.id, {"code": row.code}, x_correlation_id)
    db.commit()
    return dump_service(row)


# ---- engagements --------------------------------------------------------------------------------------------------------

@router.post("/engagements", status_code=201)
def create_engagement(payload: EngagementIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:engagement:write"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    customer = db.scalar(select(ARCustomer).where(ARCustomer.id == payload.customer_id, ARCustomer.organization_id == org))
    if not customer or customer.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "customer_not_active_or_missing"})
    if payload.service_id:
        service = db.scalar(select(ServiceDefinition).where(ServiceDefinition.id == payload.service_id, ServiceDefinition.organization_id == org))
        if not service or service.status != "Active":
            raise HTTPException(status_code=409, detail={"code": "service_not_active_or_missing"})
    data = payload.model_dump()
    data["owner_subject"] = data["owner_subject"] or principal.subject
    row = Engagement(organization_id=org, created_by=principal.subject, status="Draft", **data)
    db.add(row)
    flush_unique(db, "engagement_code_exists")
    audit(db, principal, "engagement.created", "dlv_engagement", row.id, {"code": row.code, "customer_id": row.customer_id}, x_correlation_id)
    db.commit()
    return dump_engagement(row)


@router.get("/engagements")
def list_engagements(db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:engagement:read"))], status: str | None = None, customer_id: str | None = None,
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(Engagement).where(Engagement.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(Engagement.status == status)
    if customer_id:
        stmt = stmt.where(Engagement.customer_id == customer_id)
    return [dump_engagement(e) for e in db.scalars(stmt.order_by(Engagement.created_at.desc()).offset(offset).limit(limit)).all()]


@router.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:engagement:read"))]):
    row = owned(db, Engagement, engagement_id, principal.organization_id, "Engagement", lock=False)
    milestones = db.scalars(select(Milestone).where(Milestone.engagement_id == row.id).order_by(Milestone.due_date)).all()
    return dump_engagement(row, list(milestones))


@router.post("/engagements/{engagement_id}/status")
def change_engagement_status(engagement_id: str, payload: StatusIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:engagement:manage"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    row = owned(db, Engagement, engagement_id, org, "Engagement")
    if payload.status not in ENGAGEMENT_TRANSITIONS[row.status]:
        raise HTTPException(status_code=409, detail={"code": "invalid_transition", "from": row.status, "to": payload.status})
    if payload.status == "Active" and row.status == "Draft":
        if row.created_by == principal.subject:
            raise HTTPException(status_code=403, detail="The creator of an engagement cannot activate it")
        customer = db.get(ARCustomer, row.customer_id)
        if not customer or customer.status != "Active":
            raise HTTPException(status_code=409, detail={"code": "customer_not_active"})
    if payload.status == "Completed" and db.scalar(select(func.count()).select_from(Milestone).where(Milestone.engagement_id == row.id, Milestone.status.notin_(["Accepted"]))):
        raise HTTPException(status_code=409, detail={"code": "milestones_not_accepted"})
    if payload.status in {"Completed", "Cancelled"} and db.scalar(select(func.count()).select_from(WorkOrder).where(WorkOrder.engagement_id == row.id, WorkOrder.status.in_(["Open", "Assigned", "In Progress", "Completed"]))):
        raise HTTPException(status_code=409, detail={"code": "work_orders_not_closed"})
    previous, row.status = row.status, payload.status
    audit(db, principal, "engagement.status_changed", "dlv_engagement", row.id, {"from": previous, "to": payload.status, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return dump_engagement(row)


# ---- milestones -----------------------------------------------------------------------------------------------------------

@router.post("/engagements/{engagement_id}/milestones", status_code=201)
def add_milestone(engagement_id: str, payload: MilestoneIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:engagement:write"))], x_correlation_id: Corr = None):
    eng = owned(db, Engagement, engagement_id, principal.organization_id, "Engagement")
    if eng.status in {"Completed", "Cancelled"}:
        raise HTTPException(status_code=409, detail={"code": "engagement_closed"})
    if payload.billable_amount is not None and not eng.currency:
        raise HTTPException(status_code=422, detail={"code": "engagement_has_no_currency"})
    row = Milestone(organization_id=eng.organization_id, engagement_id=eng.id, created_by=principal.subject, status="Planned", **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, principal, "milestone.created", "dlv_milestone", row.id, {"engagement_id": eng.id, "title": row.title}, x_correlation_id)
    db.commit()
    return dump_milestone(row)


@router.post("/milestones/{milestone_id}/deliver")
def deliver_milestone(milestone_id: str, payload: EvidenceIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:milestone:deliver"))], x_correlation_id: Corr = None):
    row = owned(db, Milestone, milestone_id, principal.organization_id, "Milestone")
    eng = db.get(Engagement, row.engagement_id)
    if eng.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "engagement_not_active"})
    if row.status not in {"Planned", "In Progress", "Rejected"}:
        raise HTTPException(status_code=409, detail={"code": "milestone_not_deliverable", "status": row.status})
    row.status, row.delivered_by, row.delivered_at, row.delivery_evidence = "Delivered", principal.subject, now(), payload.evidence
    row.accepted_by = row.accepted_at = row.client_acceptance_reference = None
    audit(db, principal, "milestone.delivered", "dlv_milestone", row.id, {"engagement_id": row.engagement_id}, x_correlation_id)
    db.commit()
    return dump_milestone(row)


@router.post("/milestones/{milestone_id}/acceptance")
def accept_milestone(milestone_id: str, payload: AcceptIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:milestone:accept"))], x_correlation_id: Corr = None):
    row = owned(db, Milestone, milestone_id, principal.organization_id, "Milestone")
    if row.status != "Delivered":
        raise HTTPException(status_code=409, detail={"code": "milestone_not_delivered"})
    if row.delivered_by == principal.subject:
        raise HTTPException(status_code=403, detail="The person who delivered a milestone cannot record its acceptance")
    row.status = "Accepted" if payload.decision == "accept" else "Rejected"
    row.accepted_by, row.accepted_at, row.client_acceptance_reference = principal.subject, now(), payload.client_acceptance_reference
    audit(db, principal, "milestone.acceptance_recorded", "dlv_milestone", row.id, {"decision": payload.decision, "reference": payload.client_acceptance_reference}, x_correlation_id)
    db.commit()
    return dump_milestone(row)


@router.post("/milestones/{milestone_id}/link-invoice")
def link_invoice(milestone_id: str, payload: LinkInvoiceIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:milestone:bill"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    row = owned(db, Milestone, milestone_id, org, "Milestone")
    if row.status != "Accepted" or row.billable_amount is None:
        raise HTTPException(status_code=409, detail={"code": "milestone_not_billable"})
    if row.invoice_id:
        raise HTTPException(status_code=409, detail={"code": "milestone_already_linked"})
    eng = db.get(Engagement, row.engagement_id)
    invoice = db.scalar(select(ARInvoice).where(ARInvoice.id == payload.invoice_id, ARInvoice.organization_id == org))
    if not invoice or invoice.customer_id != eng.customer_id or invoice.currency != eng.currency or invoice.status in {"Void"}:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_matching_engagement"})
    if db.scalar(select(Milestone.id).where(Milestone.invoice_id == invoice.id).limit(1)):
        raise HTTPException(status_code=409, detail={"code": "invoice_already_linked"})
    row.invoice_id = invoice.id
    audit(db, principal, "milestone.invoice_linked", "dlv_milestone", row.id, {"invoice_id": invoice.id}, x_correlation_id)
    db.commit()
    return dump_milestone(row)


# ---- work orders -----------------------------------------------------------------------------------------------------------

@router.post("/work-orders", status_code=201)
def create_work_order(payload: WorkOrderIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:write"))], x_correlation_id: Corr = None):
    if payload.engagement_id:
        eng = owned(db, Engagement, payload.engagement_id, principal.organization_id, "Engagement", lock=False)
        if eng.status in {"Completed", "Cancelled"}:
            raise HTTPException(status_code=409, detail={"code": "engagement_closed"})
    row = WorkOrder(organization_id=principal.organization_id, created_by=principal.subject, status="Open", **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, principal, "work_order.created", "dlv_work_order", row.id, {"title": row.title, "priority": row.priority}, x_correlation_id)
    db.commit()
    return dump_work_order(row)


@router.get("/work-orders")
def list_work_orders(db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:read"))], status: str | None = None, engagement_id: str | None = None,
                     assignee_employee_id: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(WorkOrder).where(WorkOrder.organization_id == principal.organization_id)
    for column, value in ((WorkOrder.status, status), (WorkOrder.engagement_id, engagement_id), (WorkOrder.assignee_employee_id, assignee_employee_id)):
        if value:
            stmt = stmt.where(column == value)
    return [dump_work_order(w) for w in db.scalars(stmt.order_by(WorkOrder.created_at.desc()).offset(offset).limit(limit)).all()]


@router.post("/work-orders/{order_id}/assign")
def assign_work_order(order_id: str, payload: AssignIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:assign"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    row = owned(db, WorkOrder, order_id, org, "Work order")
    if row.status not in {"Open", "Assigned"}:
        raise HTTPException(status_code=409, detail={"code": "work_order_not_assignable", "status": row.status})
    employee = db.scalar(select(Employee).where(Employee.id == payload.employee_id, Employee.organization_id == org))
    if not employee or employee.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "assignee_not_active_or_missing"})
    row.assignee_employee_id, row.status = employee.id, "Assigned"
    audit(db, principal, "work_order.assigned", "dlv_work_order", row.id, {"employee_id": employee.id}, x_correlation_id)
    db.commit()
    return dump_work_order(row)


@router.post("/work-orders/{order_id}/start")
def start_work_order(order_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:execute"))], x_correlation_id: Corr = None):
    row = owned(db, WorkOrder, order_id, principal.organization_id, "Work order")
    if row.status != "Assigned":
        raise HTTPException(status_code=409, detail={"code": "work_order_not_assigned", "status": row.status})
    row.status = "In Progress"
    audit(db, principal, "work_order.started", "dlv_work_order", row.id, {}, x_correlation_id)
    db.commit()
    return dump_work_order(row)


@router.post("/work-orders/{order_id}/complete")
def complete_work_order(order_id: str, payload: EvidenceIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:execute"))], x_correlation_id: Corr = None):
    row = owned(db, WorkOrder, order_id, principal.organization_id, "Work order")
    if row.status != "In Progress":
        raise HTTPException(status_code=409, detail={"code": "work_order_not_in_progress", "status": row.status})
    row.status, row.completed_by, row.completed_at, row.completion_evidence = "Completed", principal.subject, now(), payload.evidence
    audit(db, principal, "work_order.completed", "dlv_work_order", row.id, {}, x_correlation_id)
    db.commit()
    return dump_work_order(row)


@router.post("/work-orders/{order_id}/verify")
def verify_work_order(order_id: str, payload: ReviewIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:verify"))], x_correlation_id: Corr = None):
    row = owned(db, WorkOrder, order_id, principal.organization_id, "Work order")
    if row.status != "Completed":
        raise HTTPException(status_code=409, detail={"code": "work_order_not_completed", "status": row.status})
    if row.completed_by == principal.subject:
        raise HTTPException(status_code=403, detail="The person who completed a work order cannot verify it")
    if payload.decision == "approve":
        row.status, row.verified_by, row.verified_at = "Verified", principal.subject, now()
    else:
        row.status, row.completed_by, row.completed_at = "In Progress", None, None
    audit(db, principal, "work_order.verified", "dlv_work_order", row.id, {"decision": payload.decision, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return dump_work_order(row)


@router.post("/work-orders/{order_id}/cancel")
def cancel_work_order(order_id: str, payload: EvidenceIn, db: Db, principal: Annotated[Principal, Depends(require_permission("delivery:workorder:write"))], x_correlation_id: Corr = None):
    row = owned(db, WorkOrder, order_id, principal.organization_id, "Work order")
    if row.status in {"Verified", "Cancelled"}:
        raise HTTPException(status_code=409, detail={"code": "work_order_closed"})
    row.status = "Cancelled"
    audit(db, principal, "work_order.cancelled", "dlv_work_order", row.id, {"reason": payload.evidence}, x_correlation_id)
    db.commit()
    return dump_work_order(row)
