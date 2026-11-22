import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "hr_employees"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_code", name="uq_hr_employee_org_code"),
        Index("ix_hr_employee_org_name", "organization_id", "last_name", "first_name"),
        Index("ix_hr_employee_org_status", "organization_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_code: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(120))
    work_email: Mapped[str | None] = mapped_column(String(320))
    work_phone: Mapped[str | None] = mapped_column(String(64))
    employment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Preboarding")
    hire_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


class EmploymentRecord(Base):
    __tablename__ = "hr_employment_records"
    __table_args__ = (Index("ix_hr_employment_org_employee_effective", "organization_id", "employee_id", "effective_from"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(128))
    position_title: Mapped[str | None] = mapped_column(String(160))
    manager_employee_id: Mapped[str | None] = mapped_column(ForeignKey("hr_employees.id"))
    work_location: Mapped[str | None] = mapped_column(String(160))
    employment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"
    __table_args__ = (UniqueConstraint("organization_id", "template_code", name="uq_onboarding_template_org_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[str | None] = mapped_column(String(40))
    workflow_type: Mapped[str] = mapped_column(String(24), nullable=False, default="Onboarding")
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class OnboardingTaskTemplate(Base):
    __tablename__ = "onboarding_task_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_role: Mapped[str] = mapped_column(String(64), nullable=False)
    required: Mapped[bool] = mapped_column(default=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OnboardingAssignment(Base):
    __tablename__ = "onboarding_assignments"
    __table_args__ = (UniqueConstraint("organization_id", "employee_id", "template_id", name="uq_onboarding_assignment_employee_template"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("onboarding_templates.id"), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="In Progress")
    target_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    __table_args__ = (UniqueConstraint("assignment_id", "source_task_id", name="uq_onboarding_assignment_source_task"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("onboarding_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    source_task_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_role: Mapped[str] = mapped_column(String(64), nullable=False)
    required: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Pending")
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[str | None] = mapped_column(String(128))
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    assigned_to: Mapped[str | None] = mapped_column(String(128))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CompensationRecord(Base):
    __tablename__ = "pay_compensation_records"
    __table_args__ = (Index("ix_pay_comp_org_employee_effective", "organization_id", "employee_id", "effective_from"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pay_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(Text)


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (UniqueConstraint("organization_id", "period_code", name="uq_pay_period_org_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("organization_id", "run_code", name="uq_pay_run_org_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    period_id: Mapped[str] = mapped_column(ForeignKey("payroll_periods.id"), nullable=False, index=True)
    run_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayrollEntry(Base):
    __tablename__ = "payroll_entries"
    __table_args__ = (UniqueConstraint("organization_id", "run_id", "employee_id", name="uq_pay_entry_org_run_employee"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    deduction_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_references: Mapped[list | None] = mapped_column(JSON)  # approved source records [{type, id}]; lineage only, nothing is calculated from them
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class EmployeeDocument(Base):
    __tablename__ = "hr_employee_documents"
    __table_args__ = (
        Index("ix_hr_document_org_employee", "organization_id", "employee_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="Confidential")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Active")
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class EmployeeAsset(Base):
    __tablename__ = "hr_employee_assets"
    __table_args__ = (
        Index("ix_hr_asset_org_employee", "organization_id", "employee_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    asset_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    returned_on: Mapped[date | None] = mapped_column(Date)
    condition_on_issue: Mapped[str | None] = mapped_column(String(64))
    condition_on_return: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Issued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class LeaveRequest(Base):
    __tablename__ = "hr_leave_requests"
    __table_args__ = (
        Index("ix_hr_leave_org_employee_dates", "organization_id", "employee_id", "start_date", "end_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    leave_category: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Submitted")
    reviewer_subject: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class EmployeeExitCase(Base):
    __tablename__ = "hr_employee_exit_cases"
    __table_args__ = (
        Index("ix_hr_exit_org_employee", "organization_id", "employee_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    checklist_assignment_id: Mapped[str | None] = mapped_column(ForeignKey("onboarding_assignments.id"))
    planned_last_day: Mapped[date] = mapped_column(Date, nullable=False)
    reason_category: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Open")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
