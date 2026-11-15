"""Configurable leave policy and balances. EVERYTHING here is a pending-owner-policy default until an authorized person approves a policy:
days are counted as calendar days (weekends and holidays are not excluded), no accrual is applied, and balances are not enforced
unless a policy is approved AND enforce_balance is set. Nothing in this module is a statement of ASAA's actual leave rules."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from asaa_ap.database import Base, get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_people.models import Employee, LeaveRequest

POLICY_NOTE = ("PENDING OWNER POLICY: calendar days are counted (weekends and holidays are not excluded), no accrual or eligibility rules are applied, "
               "and balances are informational unless an approved policy sets enforce_balance.")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeavePolicy(Base):
    __tablename__ = "hr_leave_policies"
    __table_args__ = (UniqueConstraint("organization_id", "leave_category", name="uq_leave_policy_org_category"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    leave_category: Mapped[str] = mapped_column(String(64), nullable=False)
    annual_entitlement_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carry_over_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    enforce_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annual_entitlement_days: Decimal = Field(ge=0, le=366, max_digits=6, decimal_places=2)
    carry_over_days: Decimal = Field(default=Decimal("0"), ge=0, le=366, max_digits=6, decimal_places=2)
    enforce_balance: bool = False


router = APIRouter(prefix="/api/v1/hr", tags=["Leave Policy"])
Db = Annotated[Session, Depends(get_db)]


def dump(p: LeavePolicy) -> dict:
    return {"leave_category": p.leave_category, "annual_entitlement_days": str(p.annual_entitlement_days), "carry_over_days": str(p.carry_over_days),
            "enforce_balance": p.enforce_balance, "status": p.status, "owner_approved": p.status == "Approved", "version": p.version,
            "updated_by": p.updated_by, "approved_by": p.approved_by, "note": None if p.status == "Approved" else POLICY_NOTE}


def audit(db, principal, action, policy, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type="hr_leave_policy",
                      entity_id=policy.id, details={"leave_category": policy.leave_category, **details}, correlation_id=correlation_id))


def days_between(start: date, end: date) -> int:
    return (end - start).days + 1


def balance_for(db: Session, org: str, employee_id: str, year: int) -> list[dict]:
    first, last = date(year, 1, 1), date(year, 12, 31)
    rows = db.scalars(select(LeaveRequest).where(LeaveRequest.organization_id == org, LeaveRequest.employee_id == employee_id,
                                                 LeaveRequest.status.in_(["Approved", "Submitted"]), LeaveRequest.start_date <= last, LeaveRequest.end_date >= first)).all()
    used: dict[str, int] = {}
    pending: dict[str, int] = {}
    for r in rows:  # days are clipped to the calendar year
        n = days_between(max(r.start_date, first), min(r.end_date, last))
        (used if r.status == "Approved" else pending)[r.leave_category] = (used if r.status == "Approved" else pending).get(r.leave_category, 0) + n
    policies = {p.leave_category: p for p in db.scalars(select(LeavePolicy).where(LeavePolicy.organization_id == org)).all()}
    out = []
    for category in sorted(set(policies) | set(used) | set(pending)):
        p = policies.get(category)
        entitlement = (p.annual_entitlement_days + p.carry_over_days) if p else None
        u, q = used.get(category, 0), pending.get(category, 0)
        out.append({"leave_category": category, "entitlement_days": str(entitlement) if entitlement is not None else None, "used_days": u, "pending_days": q,
                    "remaining_days": str(entitlement - u - q) if entitlement is not None else None, "policy_status": p.status if p else "No policy configured",
                    "enforced": bool(p and p.status == "Approved" and p.enforce_balance), "note": None if p and p.status == "Approved" else POLICY_NOTE})
    return out


def check_balance(db: Session, org: str, employee_id: str, category: str, start: date, end: date) -> None:
    """Raise 409 only when an APPROVED policy with enforce_balance exists and the request would exceed the remaining days."""
    policy = db.scalar(select(LeavePolicy).where(LeavePolicy.organization_id == org, LeavePolicy.leave_category == category))
    if not policy or policy.status != "Approved" or not policy.enforce_balance:
        return
    entry = next((b for b in balance_for(db, org, employee_id, start.year) if b["leave_category"] == category), None)
    remaining = Decimal(entry["remaining_days"]) if entry and entry["remaining_days"] is not None else Decimal(0)
    if Decimal(days_between(start, end)) > remaining:
        raise HTTPException(status_code=409, detail={"code": "leave_balance_exceeded", "remaining_days": str(remaining), "requested_days": days_between(start, end)})


@router.get("/leave-policies")
def list_policies(db: Db, principal: Annotated[Principal, Depends(require_permission("hr:leave:policy:read"))]):
    return [dump(p) for p in db.scalars(select(LeavePolicy).where(LeavePolicy.organization_id == principal.organization_id).order_by(LeavePolicy.leave_category)).all()]


@router.put("/leave-policies/{category}")
def put_policy(category: str, payload: PolicyWrite, db: Db, principal: Annotated[Principal, Depends(require_permission("hr:leave:policy:write"))],
               x_correlation_id: Annotated[str | None, Header()] = None):
    if not category.strip() or len(category) > 64:
        raise HTTPException(status_code=422, detail={"code": "invalid_leave_category"})
    policy = db.scalar(select(LeavePolicy).where(LeavePolicy.organization_id == principal.organization_id, LeavePolicy.leave_category == category))
    if policy is None:
        policy = LeavePolicy(organization_id=principal.organization_id, leave_category=category, updated_by=principal.subject, **payload.model_dump())
        db.add(policy)
    else:  # any change returns the policy to pending approval
        policy.annual_entitlement_days, policy.carry_over_days, policy.enforce_balance = payload.annual_entitlement_days, payload.carry_over_days, payload.enforce_balance
        policy.status, policy.approved_by, policy.approved_at, policy.updated_by = "Pending Approval", None, None, principal.subject
    db.flush()
    audit(db, principal, "leave_policy.saved", policy, {"annual_entitlement_days": str(payload.annual_entitlement_days), "enforce_balance": payload.enforce_balance}, x_correlation_id)
    db.commit()
    db.refresh(policy)
    return dump(policy)


@router.post("/leave-policies/{category}/approve")
def approve_policy(category: str, db: Db, principal: Annotated[Principal, Depends(require_permission("hr:leave:policy:approve"))],
                   x_correlation_id: Annotated[str | None, Header()] = None):
    policy = db.scalar(select(LeavePolicy).where(LeavePolicy.organization_id == principal.organization_id, LeavePolicy.leave_category == category))
    if not policy:
        raise HTTPException(status_code=404, detail="Leave policy not found")
    if policy.status == "Approved":
        raise HTTPException(status_code=409, detail={"code": "policy_already_approved"})
    if principal.subject == policy.updated_by:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_policy"})
    policy.status, policy.approved_by, policy.approved_at = "Approved", principal.subject, utcnow()
    db.flush()
    audit(db, principal, "leave_policy.approved", policy, {}, x_correlation_id)
    db.commit()
    db.refresh(policy)
    return dump(policy)


@router.get("/employees/{employee_id}/leave-balance")
def leave_balance(employee_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("hr:leave:read"))], year: int = Query(default=None, ge=2000, le=2100)):
    if not db.scalar(select(Employee.id).where(Employee.id == employee_id, Employee.organization_id == principal.organization_id)):
        raise HTTPException(status_code=404, detail="Employee not found")
    year = year or date.today().year
    return {"employee_id": employee_id, "year": year, "balances": balance_for(db, principal.organization_id, employee_id, year)}
