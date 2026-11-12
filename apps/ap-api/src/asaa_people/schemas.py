from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCreate(StrictModel):
    employee_code: str | None = Field(default=None, max_length=64)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    work_email: str | None = Field(default=None, max_length=320)
    work_phone: str | None = Field(default=None, max_length=64)
    employment_type: str = Field(min_length=1, max_length=40)
    hire_date: date | None = None


class EmploymentRecordCreate(StrictModel):
    department_id: str | None = None
    position_title: str | None = Field(default=None, max_length=160)
    manager_employee_id: str | None = None
    work_location: str | None = Field(default=None, max_length=160)
    employment_type: str = Field(min_length=1, max_length=40)
    status: str = Field(default="Active", pattern="^(Preboarding|Active|On Leave|Suspended)$")
    effective_from: date
    effective_to: date | None = None
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def dates_valid(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self


class OnboardingTaskDefinition(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    owner_role: str = Field(min_length=1, max_length=64)
    required: bool = True
    sequence: int = Field(default=1, ge=1)


class OnboardingTemplateCreate(StrictModel):
    template_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    employment_type: str | None = Field(default=None, max_length=40)
    workflow_type: str = Field(default="Onboarding", pattern="^(Onboarding|Offboarding)$")
    tasks: list[OnboardingTaskDefinition] = Field(min_length=1, max_length=100)


class OnboardingAssignmentCreate(StrictModel):
    employee_id: str
    template_id: str
    target_date: date | None = None


class OnboardingTaskUpdate(StrictModel):
    status: str = Field(pattern="^(Pending|In Progress|Blocked|Completed|Waived)$")
    evidence_reference: str | None = Field(default=None, max_length=500)
    due_date: date | None = None


class CompensationCreate(StrictModel):
    employee_id: str
    currency: str = Field(pattern="^[A-Z]{3}$")
    pay_basis: str = Field(min_length=1, max_length=32)
    gross_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    frequency: str = Field(min_length=1, max_length=32)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates_valid(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self


class PayrollPeriodCreate(StrictModel):
    period_code: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates_valid(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class PayrollRunCreate(StrictModel):
    period_id: str
    run_code: str = Field(min_length=1, max_length=64)
    currency: str = Field(pattern="^[A-Z]{3}$")


class PayrollEntryCreate(StrictModel):
    employee_id: str
    currency: str = Field(pattern="^[A-Z]{3}$")
    gross_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    deduction_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    net_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    breakdown: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def amounts_reconcile(self):
        if self.deduction_total > self.gross_amount:
            raise ValueError("deduction_total cannot exceed gross_amount")
        if self.gross_amount - self.deduction_total != self.net_amount:
            raise ValueError("net_amount must equal gross_amount minus deduction_total")
        return self


class EmployeeDocumentCreate(StrictModel):
    document_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=180)
    storage_reference: str = Field(min_length=1, max_length=500)
    classification: str = Field(default="Confidential", pattern="^(Internal|Confidential|Restricted)$")
    issued_on: date | None = None
    expires_on: date | None = None

    @model_validator(mode="after")
    def document_dates_valid(self):
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValueError("expires_on cannot precede issued_on")
        return self


class EmployeeAssetCreate(StrictModel):
    asset_reference: str = Field(min_length=1, max_length=128)
    asset_type: str = Field(min_length=1, max_length=64)
    issued_on: date
    condition_on_issue: str | None = Field(default=None, max_length=64)


class EmployeeAssetReturn(StrictModel):
    returned_on: date
    condition_on_return: str | None = Field(default=None, max_length=64)


class LeaveRequestCreate(StrictModel):
    leave_category: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def leave_dates_valid(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class LeaveRequestReview(StrictModel):
    decision: str = Field(pattern="^(Approved|Rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)


class EmployeeExitCreate(StrictModel):
    planned_last_day: date
    reason_category: str = Field(min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=4000)
    offboarding_template_id: str | None = None


class OnboardingTemplateStatusUpdate(StrictModel):
    active: bool


class OnboardingTaskAssignment(StrictModel):
    assigned_to: str | None = Field(default=None, min_length=1, max_length=128)


class CompensationDecision(StrictModel):
    decision: str = Field(pattern="^(Approved|Rejected)$")
    approval_note: str | None = Field(default=None, max_length=2000)


class PayrollRunReview(StrictModel):
    review_note: str | None = Field(default=None, max_length=2000)


class OnboardingTemplateReplace(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    employment_type: str | None = Field(default=None, max_length=40)
    workflow_type: str | None = Field(default=None, pattern="^(Onboarding|Offboarding)$")
    tasks: list[OnboardingTaskDefinition] = Field(min_length=1, max_length=100)


class EmployeeDocumentStatusUpdate(StrictModel):
    status: str = Field(pattern="^(Active|Archived)$")


class PayrollEntryUpdate(StrictModel):
    currency: str = Field(pattern="^[A-Z]{3}$")
    gross_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    deduction_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    net_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    breakdown: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def amounts_reconcile(self):
        if self.deduction_total > self.gross_amount:
            raise ValueError("deduction_total cannot exceed gross_amount")
        if self.gross_amount - self.deduction_total != self.net_amount:
            raise ValueError("net_amount must equal gross_amount minus deduction_total")
        return self
