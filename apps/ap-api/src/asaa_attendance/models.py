import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class Shift(Base):
    __tablename__ = "att_shifts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_att_shift_org_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    work_arrangement: Mapped[str] = mapped_column(String(24), nullable=False, default="On-site")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Active")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class RosterAssignment(Base):
    __tablename__ = "att_roster_assignments"
    __table_args__ = (UniqueConstraint("organization_id", "employee_id", "work_date", name="uq_att_roster_employee_date"),
                      Index("ix_att_roster_org_date", "organization_id", "work_date"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    shift_id: Mapped[str] = mapped_column(ForeignKey("att_shifts.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Holiday(Base):
    __tablename__ = "att_holidays"
    __table_args__ = (UniqueConstraint("organization_id", "holiday_date", "name", name="uq_att_holiday_org_date_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AttendancePolicy(Base):
    """One row per organization. Overtime is computed only once the policy is Approved by someone other than its maker."""
    __tablename__ = "att_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    overtime_threshold_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttendanceRecord(Base):
    __tablename__ = "att_records"
    __table_args__ = (Index("ix_att_record_org_employee_date", "organization_id", "employee_id", "work_date"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="self")
    worked_minutes: Mapped[int | None] = mapped_column(Integer)
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_status: Mapped[str] = mapped_column(String(16), nullable=False, default="None")
    overtime_reviewed_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AttendanceCorrection(Base):
    __tablename__ = "att_corrections"
    __table_args__ = (Index("ix_att_correction_org_status", "organization_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    record_id: Mapped[str | None] = mapped_column(ForeignKey("att_records.id"))
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_clock_out: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Pending")
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
