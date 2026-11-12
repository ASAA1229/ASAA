import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from asaa_ap.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Timesheet(Base):
    __tablename__ = "work_timesheets"
    __table_args__ = (Index("ix_work_timesheet_org_employee_period", "organization_id", "employee_subject", "period_start", "period_end"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    employee_reference: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[object] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    total_hours: Mapped[object] = mapped_column(Numeric(9, 2), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    __mapper_args__ = {"version_id_col": version}
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))

class TimeEntry(Base):
    __tablename__ = "work_time_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timesheet_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_date: Mapped[object] = mapped_column(Date, nullable=False)
    project_reference: Mapped[str | None] = mapped_column(String(160))
    task_reference: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    hours: Mapped[object] = mapped_column(Numeric(7, 2), nullable=False)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class ExpenseClaim(Base):
    __tablename__ = "expense_claims"
    __table_args__ = (Index("ix_expense_claim_org_employee_status", "organization_id", "employee_subject", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    expense_date: Mapped[object] = mapped_column(Date, nullable=False)
    category_code: Mapped[str] = mapped_column(String(80), nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    receipt_reference: Mapped[str | None] = mapped_column(String(500))
    project_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    __mapper_args__ = {"version_id_col": version}
    reimbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reimbursed_by: Mapped[str | None] = mapped_column(String(128))
    reimbursement_reference: Mapped[str | None] = mapped_column(String(200))
