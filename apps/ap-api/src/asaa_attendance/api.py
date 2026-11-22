"""Attendance, shifts, rosters and holidays.

Self-service clock-in/out resolves the caller's employee record through the authoritative identity link. Work dates are UTC dates until
the owner sets an organization time zone. Overtime is computed only when the attendance policy has been approved by someone other than
its maker (BLOCKED - OWNER: the overtime threshold); no premium pay or pay rule is applied here. Corrections and overtime need an
independent reviewer.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_attendance.models import AttendanceCorrection, AttendancePolicy, AttendanceRecord, Holiday, RosterAssignment, Shift
from asaa_identity.models import IdentitySubjectLink
from asaa_people.models import Employee, LeaveRequest

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance and Shifts"])
Db = Annotated[Session, Depends(get_db)]
Corr = Annotated[str | None, Header()]
ARRANGEMENTS = ("On-site", "Remote", "Field", "Hybrid")


def now() -> datetime:
    return datetime.now(timezone.utc)


def audit(db: Session, principal: Principal, action: str, kind: str, entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=kind, entity_id=entity_id,
                      details=details, correlation_id=correlation_id))


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def own_employee(db: Session, principal: Principal) -> str:
    link = db.scalar(select(IdentitySubjectLink).where(IdentitySubjectLink.organization_id == principal.organization_id, IdentitySubjectLink.subject == principal.subject))
    if not link:
        raise HTTPException(status_code=409, detail={"code": "no_employee_link", "message": "Your identity is not linked to an employee record"})
    return link.employee_id


def employee_in_org(db: Session, employee_id: str, org: str) -> Employee:
    row = db.scalar(select(Employee).where(Employee.id == employee_id, Employee.organization_id == org))
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    return row


def scoped_employee(db: Session, principal: Principal, employee_id: str | None) -> str | None:
    """Own records unless the caller can read all; returns None only for an all-employee query."""
    if "attendance:record:read:all" in principal.permissions:
        if employee_id:
            employee_in_org(db, employee_id, principal.organization_id)
        return employee_id
    own = own_employee(db, principal)
    if employee_id and employee_id != own:
        raise HTTPException(status_code=403, detail="Permission denied")
    return own


# ---- schemas ---------------------------------------------------------------------------------------------------------

class ShiftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=120)
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0, le=480)
    work_arrangement: Literal["On-site", "Remote", "Field", "Hybrid"] = "On-site"


class RosterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=36)
    shift_id: str = Field(min_length=1, max_length=36)
    work_date: date


class HolidayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    holiday_date: date
    name: str = Field(min_length=2, max_length=160)
    optional: bool = False


class PolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overtime_threshold_minutes: int | None = Field(default=None, ge=1, le=1440)


class CorrectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str | None = Field(default=None, max_length=36)
    work_date: date
    requested_clock_in: datetime
    requested_clock_out: datetime
    reason: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def ordered(self):
        if aware(self.requested_clock_out) <= aware(self.requested_clock_in):
            raise ValueError("requested_clock_out must be after requested_clock_in")
        if aware(self.requested_clock_out) - aware(self.requested_clock_in) > timedelta(hours=24):
            raise ValueError("a single attendance interval cannot exceed 24 hours")
        return self


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


def dump_shift(s: Shift) -> dict:
    return {"id": s.id, "code": s.code, "name": s.name, "start_time": s.start_time.isoformat(), "end_time": s.end_time.isoformat(), "break_minutes": s.break_minutes,
            "work_arrangement": s.work_arrangement, "status": s.status}


def dump_record(r: AttendanceRecord) -> dict:
    return {"id": r.id, "employee_id": r.employee_id, "work_date": r.work_date.isoformat(), "clock_in": r.clock_in.isoformat(), "clock_out": r.clock_out.isoformat() if r.clock_out else None,
            "source": r.source, "worked_minutes": r.worked_minutes, "overtime_minutes": r.overtime_minutes, "overtime_status": r.overtime_status}


def dump_correction(c: AttendanceCorrection) -> dict:
    return {"id": c.id, "employee_id": c.employee_id, "record_id": c.record_id, "work_date": c.work_date.isoformat(), "requested_clock_in": c.requested_clock_in.isoformat(),
            "requested_clock_out": c.requested_clock_out.isoformat(), "reason": c.reason, "status": c.status, "requested_by": c.requested_by, "reviewed_by": c.reviewed_by,
            "review_reason": c.review_reason}


# ---- shifts, roster, holidays ------------------------------------------------------------------------------------------

@router.post("/shifts", status_code=201)
def create_shift(payload: ShiftIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:shift:write"))], x_correlation_id: Corr = None):
    row = Shift(organization_id=principal.organization_id, created_by=principal.subject, **payload.model_dump())
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_code_exists"}) from None
    audit(db, principal, "shift.created", "att_shift", row.id, {"code": row.code}, x_correlation_id)
    db.commit()
    return dump_shift(row)


@router.get("/shifts")
def list_shifts(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:shift:read"))], include_retired: bool = False):
    stmt = select(Shift).where(Shift.organization_id == principal.organization_id)
    if not include_retired:
        stmt = stmt.where(Shift.status == "Active")
    return [dump_shift(s) for s in db.scalars(stmt.order_by(Shift.code)).all()]


@router.post("/shifts/{shift_id}/retire")
def retire_shift(shift_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:shift:write"))], x_correlation_id: Corr = None):
    row = db.scalar(select(Shift).where(Shift.id == shift_id, Shift.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Shift not found")
    row.status = "Retired"
    audit(db, principal, "shift.retired", "att_shift", row.id, {"code": row.code}, x_correlation_id)
    db.commit()
    return dump_shift(row)


@router.put("/roster")
def assign_roster(payload: RosterIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:roster:write"))], x_correlation_id: Corr = None):
    org = principal.organization_id
    employee_in_org(db, payload.employee_id, org)
    shift = db.scalar(select(Shift).where(Shift.id == payload.shift_id, Shift.organization_id == org))
    if not shift or shift.status != "Active":
        raise HTTPException(status_code=404, detail="Active shift not found")
    if db.scalar(select(LeaveRequest.id).where(LeaveRequest.organization_id == org, LeaveRequest.employee_id == payload.employee_id, LeaveRequest.status == "Approved",
                                               LeaveRequest.start_date <= payload.work_date, LeaveRequest.end_date >= payload.work_date).limit(1)):
        raise HTTPException(status_code=409, detail={"code": "employee_on_approved_leave"})
    if db.scalar(select(Holiday.id).where(Holiday.organization_id == org, Holiday.holiday_date == payload.work_date, Holiday.optional.is_(False)).limit(1)):
        raise HTTPException(status_code=409, detail={"code": "date_is_holiday"})
    row = db.scalar(select(RosterAssignment).where(RosterAssignment.organization_id == org, RosterAssignment.employee_id == payload.employee_id, RosterAssignment.work_date == payload.work_date))
    if row:
        row.shift_id = shift.id
    else:
        row = RosterAssignment(organization_id=org, employee_id=payload.employee_id, shift_id=shift.id, work_date=payload.work_date, created_by=principal.subject)
        db.add(row)
    db.flush()
    audit(db, principal, "roster.assigned", "att_roster", row.id, {"employee_id": row.employee_id, "shift_id": shift.id, "work_date": payload.work_date.isoformat()}, x_correlation_id)
    db.commit()
    return {"id": row.id, "employee_id": row.employee_id, "shift_id": row.shift_id, "work_date": row.work_date.isoformat()}


@router.get("/roster")
def list_roster(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:roster:read"))], date_from: date, date_to: date,
                employee_id: str | None = None):
    if date_to < date_from or (date_to - date_from).days > 92:
        raise HTTPException(status_code=422, detail={"code": "invalid_range", "message": "date_to must not precede date_from and the range is limited to 92 days"})
    stmt = select(RosterAssignment).where(RosterAssignment.organization_id == principal.organization_id, RosterAssignment.work_date >= date_from, RosterAssignment.work_date <= date_to)
    if employee_id:
        stmt = stmt.where(RosterAssignment.employee_id == employee_id)
    return [{"id": r.id, "employee_id": r.employee_id, "shift_id": r.shift_id, "work_date": r.work_date.isoformat()} for r in db.scalars(stmt.order_by(RosterAssignment.work_date)).all()]


@router.delete("/roster/{assignment_id}", status_code=204)
def remove_roster(assignment_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:roster:write"))], x_correlation_id: Corr = None):
    row = db.scalar(select(RosterAssignment).where(RosterAssignment.id == assignment_id, RosterAssignment.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Roster assignment not found")
    audit(db, principal, "roster.removed", "att_roster", row.id, {"employee_id": row.employee_id, "work_date": row.work_date.isoformat()}, x_correlation_id)
    db.delete(row)
    db.commit()


@router.post("/holidays", status_code=201)
def create_holiday(payload: HolidayIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:holiday:write"))], x_correlation_id: Corr = None):
    row = Holiday(organization_id=principal.organization_id, created_by=principal.subject, **payload.model_dump())
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "holiday_exists"}) from None
    audit(db, principal, "holiday.created", "att_holiday", row.id, {"date": payload.holiday_date.isoformat(), "name": payload.name}, x_correlation_id)
    db.commit()
    return {"id": row.id, "holiday_date": row.holiday_date.isoformat(), "name": row.name, "optional": row.optional}


@router.get("/holidays")
def list_holidays(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:holiday:read"))], year: int | None = Query(default=None, ge=2000, le=2100)):
    stmt = select(Holiday).where(Holiday.organization_id == principal.organization_id)
    if year:
        stmt = stmt.where(Holiday.holiday_date >= date(year, 1, 1), Holiday.holiday_date <= date(year, 12, 31))
    return [{"id": h.id, "holiday_date": h.holiday_date.isoformat(), "name": h.name, "optional": h.optional} for h in db.scalars(stmt.order_by(Holiday.holiday_date)).all()]


@router.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:holiday:write"))], x_correlation_id: Corr = None):
    row = db.scalar(select(Holiday).where(Holiday.id == holiday_id, Holiday.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Holiday not found")
    audit(db, principal, "holiday.deleted", "att_holiday", row.id, {"date": row.holiday_date.isoformat(), "name": row.name}, x_correlation_id)
    db.delete(row)
    db.commit()


# ---- policy (overtime threshold, owner-approved) -----------------------------------------------------------------------

def dump_policy(p: AttendancePolicy | None) -> dict:
    if not p:
        return {"status": "No policy configured", "overtime_threshold_minutes": None, "overtime_enabled": False,
                "note": "BLOCKED - OWNER: overtime threshold is an owner policy value. Overtime is not computed until a policy is approved."}
    return {"status": p.status, "overtime_threshold_minutes": p.overtime_threshold_minutes, "updated_by": p.updated_by, "approved_by": p.approved_by,
            "overtime_enabled": p.status == "Approved" and p.overtime_threshold_minutes is not None}


def approved_threshold(db: Session, org: str) -> int | None:
    p = db.scalar(select(AttendancePolicy).where(AttendancePolicy.organization_id == org))
    return p.overtime_threshold_minutes if p and p.status == "Approved" else None


@router.get("/policy")
def get_policy(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:policy:read"))]):
    return dump_policy(db.scalar(select(AttendancePolicy).where(AttendancePolicy.organization_id == principal.organization_id)))


@router.put("/policy")
def put_policy(payload: PolicyIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:policy:write"))], x_correlation_id: Corr = None):
    row = db.scalar(select(AttendancePolicy).where(AttendancePolicy.organization_id == principal.organization_id))
    if not row:
        row = AttendancePolicy(organization_id=principal.organization_id, updated_by=principal.subject)
        db.add(row)
    row.overtime_threshold_minutes, row.status, row.updated_by, row.approved_by, row.approved_at = payload.overtime_threshold_minutes, "Pending Approval", principal.subject, None, None
    db.flush()
    audit(db, principal, "attendance_policy.updated", "att_policy", row.id, {"overtime_threshold_minutes": row.overtime_threshold_minutes}, x_correlation_id)
    db.commit()
    return dump_policy(row)


@router.post("/policy/approve")
def approve_policy(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:policy:approve"))], x_correlation_id: Corr = None):
    row = db.scalar(select(AttendancePolicy).where(AttendancePolicy.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Attendance policy not found")
    if row.status == "Approved":
        raise HTTPException(status_code=409, detail={"code": "policy_already_approved"})
    if row.updated_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_policy"})
    row.status, row.approved_by, row.approved_at = "Approved", principal.subject, now()
    audit(db, principal, "attendance_policy.approved", "att_policy", row.id, {"overtime_threshold_minutes": row.overtime_threshold_minutes}, x_correlation_id)
    db.commit()
    return dump_policy(row)


# ---- clock events and records --------------------------------------------------------------------------------------------

def finalize(db: Session, record: AttendanceRecord) -> None:
    """Compute worked and (policy permitting) overtime minutes for a closed record."""
    elapsed = int((aware(record.clock_out) - aware(record.clock_in)).total_seconds() // 60)
    shift = db.scalar(select(Shift).join(RosterAssignment, RosterAssignment.shift_id == Shift.id).where(
        RosterAssignment.organization_id == record.organization_id, RosterAssignment.employee_id == record.employee_id, RosterAssignment.work_date == record.work_date))
    record.worked_minutes = max(0, elapsed - (shift.break_minutes if shift else 0))
    threshold = approved_threshold(db, record.organization_id)
    over = max(0, record.worked_minutes - threshold) if threshold is not None else 0
    record.overtime_minutes, record.overtime_status = over, "Pending" if over else "None"
    record.overtime_reviewed_by = None


@router.post("/clock-in", status_code=201)
def clock_in(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:clock"))], x_correlation_id: Corr = None):
    employee_id = own_employee(db, principal)
    employee = employee_in_org(db, employee_id, principal.organization_id)
    if employee.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "employee_not_active", "status": employee.status})
    if db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.organization_id == principal.organization_id, AttendanceRecord.employee_id == employee_id,
                                                   AttendanceRecord.clock_out.is_(None)).limit(1)):
        raise HTTPException(status_code=409, detail={"code": "already_clocked_in"})
    stamp = now()
    row = AttendanceRecord(organization_id=principal.organization_id, employee_id=employee_id, work_date=stamp.date(), clock_in=stamp, source="self")
    db.add(row)
    db.flush()
    audit(db, principal, "attendance.clock_in", "att_record", row.id, {"work_date": row.work_date.isoformat()}, x_correlation_id)
    db.commit()
    return dump_record(row)


@router.post("/clock-out")
def clock_out(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:clock"))], x_correlation_id: Corr = None):
    employee_id = own_employee(db, principal)
    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.organization_id == principal.organization_id, AttendanceRecord.employee_id == employee_id,
                                                   AttendanceRecord.clock_out.is_(None)).with_for_update())
    if not row:
        raise HTTPException(status_code=409, detail={"code": "not_clocked_in"})
    row.clock_out = now()
    if row.clock_out - aware(row.clock_in) > timedelta(hours=24):
        raise HTTPException(status_code=409, detail={"code": "open_record_too_long", "message": "Submit an attendance correction for this record"})
    finalize(db, row)
    audit(db, principal, "attendance.clock_out", "att_record", row.id, {"worked_minutes": row.worked_minutes, "overtime_minutes": row.overtime_minutes}, x_correlation_id)
    db.commit()
    return dump_record(row)


@router.get("/records")
def list_records(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:record:read"))], date_from: date, date_to: date, employee_id: str | None = None,
                 limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail={"code": "invalid_range"})
    scope = scoped_employee(db, principal, employee_id)
    stmt = select(AttendanceRecord).where(AttendanceRecord.organization_id == principal.organization_id, AttendanceRecord.work_date >= date_from, AttendanceRecord.work_date <= date_to)
    if scope:
        stmt = stmt.where(AttendanceRecord.employee_id == scope)
    return [dump_record(r) for r in db.scalars(stmt.order_by(AttendanceRecord.clock_in.desc()).offset(offset).limit(limit)).all()]


@router.post("/records/{record_id}/overtime-review")
def review_overtime(record_id: str, payload: ReviewIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:overtime:review"))], x_correlation_id: Corr = None):
    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.id == record_id, AttendanceRecord.organization_id == principal.organization_id).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if row.overtime_status != "Pending":
        raise HTTPException(status_code=409, detail={"code": "no_pending_overtime"})
    link = db.scalar(select(IdentitySubjectLink).where(IdentitySubjectLink.organization_id == principal.organization_id, IdentitySubjectLink.employee_id == row.employee_id))
    if link and link.subject == principal.subject:
        raise HTTPException(status_code=403, detail="Employees cannot review their own overtime")
    row.overtime_status = "Approved" if payload.decision == "approve" else "Rejected"
    row.overtime_reviewed_by = principal.subject
    audit(db, principal, "attendance.overtime_reviewed", "att_record", row.id, {"decision": payload.decision, "overtime_minutes": row.overtime_minutes, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return dump_record(row)


# ---- corrections -----------------------------------------------------------------------------------------------------------

@router.post("/corrections", status_code=201)
def request_correction(payload: CorrectionIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:correction:request"))], x_correlation_id: Corr = None):
    employee_id = own_employee(db, principal)
    if payload.record_id:
        rec = db.scalar(select(AttendanceRecord).where(AttendanceRecord.id == payload.record_id, AttendanceRecord.organization_id == principal.organization_id,
                                                       AttendanceRecord.employee_id == employee_id))
        if not rec:
            raise HTTPException(status_code=404, detail="Attendance record not found")
    row = AttendanceCorrection(organization_id=principal.organization_id, employee_id=employee_id, record_id=payload.record_id, work_date=payload.work_date,
                               requested_clock_in=aware(payload.requested_clock_in), requested_clock_out=aware(payload.requested_clock_out), reason=payload.reason,
                               status="Pending", requested_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "attendance_correction.requested", "att_correction", row.id, {"work_date": payload.work_date.isoformat()}, x_correlation_id)
    db.commit()
    return dump_correction(row)


@router.get("/corrections")
def list_corrections(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:correction:read"))], status: str | None = None,
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(AttendanceCorrection).where(AttendanceCorrection.organization_id == principal.organization_id)
    if "attendance:record:read:all" not in principal.permissions:
        stmt = stmt.where(AttendanceCorrection.requested_by == principal.subject)
    if status:
        stmt = stmt.where(AttendanceCorrection.status == status)
    return [dump_correction(c) for c in db.scalars(stmt.order_by(AttendanceCorrection.created_at.desc()).offset(offset).limit(limit)).all()]


@router.post("/corrections/{correction_id}/review")
def review_correction(correction_id: str, payload: ReviewIn, db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:correction:review"))], x_correlation_id: Corr = None):
    row = db.scalar(select(AttendanceCorrection).where(AttendanceCorrection.id == correction_id, AttendanceCorrection.organization_id == principal.organization_id).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Attendance correction not found")
    if row.requested_by == principal.subject:
        raise HTTPException(status_code=403, detail="Requesters cannot review their own correction")
    if row.status != "Pending":
        raise HTTPException(status_code=409, detail={"code": "correction_not_pending"})
    row.status = "Approved" if payload.decision == "approve" else "Rejected"
    row.reviewed_by, row.reviewed_at, row.review_reason = principal.subject, now(), payload.reason
    if payload.decision == "approve":
        record = db.get(AttendanceRecord, row.record_id) if row.record_id else None
        if record:
            record.clock_in, record.clock_out, record.source = row.requested_clock_in, row.requested_clock_out, "correction"
        else:
            record = AttendanceRecord(organization_id=row.organization_id, employee_id=row.employee_id, work_date=row.work_date, clock_in=row.requested_clock_in,
                                      clock_out=row.requested_clock_out, source="correction")
            db.add(record)
        db.flush()
        finalize(db, record)
    audit(db, principal, "attendance_correction.reviewed", "att_correction", row.id, {"decision": payload.decision, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return dump_correction(row)


# ---- summary ----------------------------------------------------------------------------------------------------------------

@router.get("/summary")
def summary(db: Db, principal: Annotated[Principal, Depends(require_permission("attendance:record:read"))], date_from: date, date_to: date, employee_id: str | None = None):
    """Per employee: worked minutes, rostered days, rostered days without attendance (excluding approved leave and holidays) and overtime."""
    if date_to < date_from or (date_to - date_from).days > 92:
        raise HTTPException(status_code=422, detail={"code": "invalid_range"})
    org = principal.organization_id
    scope = scoped_employee(db, principal, employee_id)
    rec_stmt = select(AttendanceRecord).where(AttendanceRecord.organization_id == org, AttendanceRecord.work_date >= date_from, AttendanceRecord.work_date <= date_to)
    ros_stmt = select(RosterAssignment).where(RosterAssignment.organization_id == org, RosterAssignment.work_date >= date_from, RosterAssignment.work_date <= date_to)
    if scope:
        rec_stmt, ros_stmt = rec_stmt.where(AttendanceRecord.employee_id == scope), ros_stmt.where(RosterAssignment.employee_id == scope)
    records, rosters = db.scalars(rec_stmt).all(), db.scalars(ros_stmt).all()
    holidays = {h.holiday_date for h in db.scalars(select(Holiday).where(Holiday.organization_id == org, Holiday.optional.is_(False), Holiday.holiday_date >= date_from, Holiday.holiday_date <= date_to))}
    leaves = db.scalars(select(LeaveRequest).where(LeaveRequest.organization_id == org, LeaveRequest.status == "Approved", LeaveRequest.start_date <= date_to, LeaveRequest.end_date >= date_from)).all()
    out: dict[str, dict] = {}

    def bucket(eid: str) -> dict:
        return out.setdefault(eid, {"employee_id": eid, "worked_minutes": 0, "rostered_days": 0, "days_without_attendance": 0, "overtime_pending_minutes": 0, "overtime_approved_minutes": 0, "open_records": 0})

    present = {(r.employee_id, r.work_date) for r in records}
    for r in records:
        b = bucket(r.employee_id)
        b["worked_minutes"] += r.worked_minutes or 0
        b["open_records"] += 1 if r.clock_out is None else 0
        if r.overtime_status == "Pending":
            b["overtime_pending_minutes"] += r.overtime_minutes
        elif r.overtime_status == "Approved":
            b["overtime_approved_minutes"] += r.overtime_minutes
    for a in rosters:
        b = bucket(a.employee_id)
        b["rostered_days"] += 1
        on_leave = any(l.employee_id == a.employee_id and l.start_date <= a.work_date <= l.end_date for l in leaves)
        if (a.employee_id, a.work_date) not in present and a.work_date not in holidays and not on_leave and a.work_date < now().date():
            b["days_without_attendance"] += 1
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "generated_at": now().isoformat(),
            "sources": ["att_records", "att_roster_assignments", "att_holidays", "hr_leave_requests"], "overtime_policy": dump_policy(db.scalar(select(AttendancePolicy).where(AttendancePolicy.organization_id == org)))["status"],
            "employees": list(out.values())}
