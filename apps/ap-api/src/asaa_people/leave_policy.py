"""Configurable leave policy and balances. EVERYTHING here is a pending-owner-policy default until an authorized person approves a policy:
days are counted as calendar days (weekends and holidays are not excluded), no accrual is applied, and balances are not enforced
unless a policy is approved AND enforce_balance is set. Nothing in this module is a statement of ASAA's actual leave rules."""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Boolean, false, DateTime, Integer, Numeric, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from asaa_ap.database import Base, get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_attendance.models import Holiday
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
    # Owner-chosen counting and accrual rules; they apply only once the policy is Approved. Defaults keep the pending-owner-policy behaviour.
    count_mode: Mapped[str] = mapped_column(String(12), nullable=False, default="calendar", server_default="calendar")  # calendar | working
    weekend_days: Mapped[list | None] = mapped_column(JSON)  # weekday numbers, Monday=0; required (may be empty) when count_mode is working
    exclude_holidays: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())  # skip the org's non-optional holidays
    accrual_mode: Mapped[str] = mapped_column(String(12), nullable=False, default="annual", server_default="annual")  # annual (up front) | monthly


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annual_entitlement_days: Decimal = Field(ge=0, le=366, max_digits=6, decimal_places=2)
    carry_over_days: Decimal = Field(default=Decimal("0"), ge=0, le=366, max_digits=6, decimal_places=2)
    enforce_balance: bool = False
    count_mode: str = Field(default="calendar", pattern="^(calendar|working)$")
    weekend_days: list[int] | None = Field(default=None, max_length=7)
    exclude_holidays: bool = False
    accrual_mode: str = Field(default="annual", pattern="^(annual|monthly)$")

    @model_validator(mode="after")
    def counting_rules_complete(self):
        if self.weekend_days is not None and (any(d < 0 or d > 6 for d in self.weekend_days) or len(set(self.weekend_days)) != len(self.weekend_days)):
            raise ValueError("weekend_days must be unique weekday numbers 0 (Monday) to 6 (Sunday)")
        if self.count_mode == "working" and self.weekend_days is None:
            raise ValueError("weekend_days is an owner policy value and must be set (an empty list means no weekend) when count_mode is working")
        if self.count_mode == "calendar" and (self.weekend_days or self.exclude_holidays):
            raise ValueError("weekend_days and exclude_holidays apply only when count_mode is working")
        return self


router = APIRouter(prefix="/api/v1/hr", tags=["Leave Policy"])
Db = Annotated[Session, Depends(get_db)]


def dump(p: LeavePolicy) -> dict:
    return {"leave_category": p.leave_category, "annual_entitlement_days": str(p.annual_entitlement_days), "carry_over_days": str(p.carry_over_days),
            "enforce_balance": p.enforce_balance, "count_mode": p.count_mode, "weekend_days": p.weekend_days, "exclude_holidays": p.exclude_holidays,
            "accrual_mode": p.accrual_mode, "status": p.status, "owner_approved": p.status == "Approved", "version": p.version,
            "updated_by": p.updated_by, "approved_by": p.approved_by, "note": None if p.status == "Approved" else POLICY_NOTE}


def audit(db, principal, action, policy, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type="hr_leave_policy",
                      entity_id=policy.id, details={"leave_category": policy.leave_category, **details}, correlation_id=correlation_id))


def days_between(start: date, end: date) -> int:
    return (end - start).days + 1


def approved_policy(db: Session, org: str, category: str) -> LeavePolicy | None:
    policy = db.scalar(select(LeavePolicy).where(LeavePolicy.organization_id == org, LeavePolicy.leave_category == category))
    return policy if policy and policy.status == "Approved" else None


def count_days(db: Session, org: str, policy: LeavePolicy | None, start: date, end: date) -> int:
    """Calendar days unless an APPROVED policy sets count_mode=working: then the owner's weekend days and (optionally) the org's non-optional holidays are skipped."""
    if policy is None or policy.status != "Approved" or policy.count_mode != "working":
        return days_between(start, end)
    skip = set(policy.weekend_days or [])
    holidays = set(db.scalars(select(Holiday.holiday_date).where(Holiday.organization_id == org, Holiday.optional.is_(False),
                                                                 Holiday.holiday_date >= start, Holiday.holiday_date <= end)).all()) if policy.exclude_holidays else set()
    return sum(1 for i in range(days_between(start, end)) if (start + timedelta(days=i)).weekday() not in skip and (start + timedelta(days=i)) not in holidays)


def accrued_days(policy: LeavePolicy | None, year: int, as_of: date) -> Decimal | None:
    """Entitlement available for the year as of a date. Annual mode (and any unapproved policy) grants the full entitlement up front; monthly mode (approved only)
    accrues 1/12 of the annual entitlement at the start of each month, rounded half up to 0.01. Carry-over is available from the start of the year."""
    if policy is None:
        return None
    total = Decimal(policy.annual_entitlement_days)
    if policy.status == "Approved" and policy.accrual_mode == "monthly":
        months = 12 if as_of.year > year else (0 if as_of.year < year else as_of.month)
        total = (total * months / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return total + Decimal(policy.carry_over_days)


def balance_for(db: Session, org: str, employee_id: str, year: int, as_of: date | None = None) -> list[dict]:
    first, last = date(year, 1, 1), date(year, 12, 31)
    as_of = as_of or date.today()
    rows = db.scalars(select(LeaveRequest).where(LeaveRequest.organization_id == org, LeaveRequest.employee_id == employee_id,
                                                 LeaveRequest.status.in_(["Approved", "Submitted"]), LeaveRequest.start_date <= last, LeaveRequest.end_date >= first)).all()
    policies = {p.leave_category: p for p in db.scalars(select(LeavePolicy).where(LeavePolicy.organization_id == org)).all()}
    used: dict[str, int] = {}
    pending: dict[str, int] = {}
    for r in rows:  # days are clipped to the calendar year and counted under the category's approved policy
        n = count_days(db, org, policies.get(r.leave_category), max(r.start_date, first), min(r.end_date, last))
        bucket = used if r.status == "Approved" else pending
        bucket[r.leave_category] = bucket.get(r.leave_category, 0) + n
    out = []
    for category in sorted(set(policies) | set(used) | set(pending)):
        p = policies.get(category)
        entitlement = accrued_days(p, year, as_of)
        u, q = used.get(category, 0), pending.get(category, 0)
        ok = bool(p and p.status == "Approved")
        out.append({"leave_category": category, "entitlement_days": str(entitlement) if entitlement is not None else None, "used_days": u, "pending_days": q,
                    "remaining_days": str(entitlement - u - q) if entitlement is not None else None, "policy_status": p.status if p else "No policy configured",
                    "enforced": bool(ok and p.enforce_balance), "accrual_mode": p.accrual_mode if ok else None,
                    "count_mode": p.count_mode if ok else "calendar", "note": None if ok else POLICY_NOTE})
    return out


def check_balance(db: Session, org: str, employee_id: str, category: str, start: date, end: date) -> None:
    """Under an APPROVED policy: refuse a request with no countable days (422) and, when enforce_balance is set, one that exceeds the remaining days (409).
    A request spanning years is checked per calendar year against the entitlement accrued by the end of its portion in that year."""
    policy = approved_policy(db, org, category)
    if policy is None:
        return
    if count_days(db, org, policy, start, end) == 0:
        raise HTTPException(status_code=422, detail={"code": "leave_has_no_working_days", "message": "Every requested day is a weekend or holiday under the approved leave policy."})
    if not policy.enforce_balance:
        return
    for year in range(start.year, end.year + 1):
        part_start, part_end = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
        requested = count_days(db, org, policy, part_start, part_end)
        entry = next((b for b in balance_for(db, org, employee_id, year, as_of=part_end) if b["leave_category"] == category), None)
        remaining = Decimal(entry["remaining_days"]) if entry and entry["remaining_days"] is not None else Decimal(0)
        if Decimal(requested) > remaining:
            raise HTTPException(status_code=409, detail={"code": "leave_balance_exceeded", "year": year, "remaining_days": str(remaining), "requested_days": requested})


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
        policy.count_mode, policy.weekend_days, policy.exclude_holidays, policy.accrual_mode = payload.count_mode, payload.weekend_days, payload.exclude_holidays, payload.accrual_mode
        policy.status, policy.approved_by, policy.approved_at, policy.updated_by = "Pending Approval", None, None, principal.subject
    db.flush()
    audit(db, principal, "leave_policy.saved", policy, {"annual_entitlement_days": str(payload.annual_entitlement_days), "enforce_balance": payload.enforce_balance,
                                                                  "count_mode": payload.count_mode, "accrual_mode": payload.accrual_mode, "exclude_holidays": payload.exclude_holidays}, x_correlation_id)
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
