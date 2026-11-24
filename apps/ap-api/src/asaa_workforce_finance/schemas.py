from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal

class TimeEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_date: date
    project_reference: str | None = Field(default=None, max_length=160)
    task_reference: str | None = Field(default=None, max_length=160)
    description: str = Field(min_length=2, max_length=1000)
    hours: Decimal = Field(gt=0, le=24, decimal_places=2)
    billable: bool = False

class TimesheetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_reference: str | None = Field(default=None, max_length=128)
    period_start: date
    period_end: date
    entries: list[TimeEntryCreate] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if any(e.work_date < self.period_start or e.work_date > self.period_end for e in self.entries):
            raise ValueError("every entry date must be inside the timesheet period")
        if sum((e.hours for e in self.entries), Decimal("0")) > Decimal("744"):
            raise ValueError("timesheet total exceeds the maximum calendar-month bound")
        return self

class TimesheetReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"] | None = None
    reason: str = Field(min_length=3, max_length=1000)
    expected_version: int = Field(ge=1)

class TimesheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    employee_subject: str
    employee_reference: str | None
    period_start: date
    period_end: date
    status: str
    total_hours: Decimal
    version: int
    created_at: datetime
    created_by: str
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_reason: str | None

class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expense_date: date
    category_code: str = Field(min_length=2, max_length=80)
    merchant: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=2, max_length=1000)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    receipt_reference: str | None = Field(default=None, max_length=500)
    project_reference: str | None = Field(default=None, max_length=160)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value):
        value = value.upper()
        if not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value

class ExpenseReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"] | None = None
    reason: str = Field(min_length=3, max_length=1000)
    expected_version: int = Field(ge=1)

class ExpenseReimbursement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reimbursement_reference: str = Field(min_length=2, max_length=200)
    expected_version: int = Field(ge=1)

class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    employee_subject: str
    expense_date: date
    category_code: str
    merchant: str | None
    description: str
    amount: Decimal
    currency: str
    receipt_reference: str | None
    project_reference: str | None
    status: str
    version: int
    created_at: datetime
    created_by: str
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_reason: str | None
    reimbursed_at: datetime | None
    reimbursed_by: str | None
    reimbursement_reference: str | None
    policy_flags: list | None = None


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Replacement of a Draft or Rejected claim's content by its owner (resubmission after rejection)."""
    expense_date: date
    category_code: str = Field(min_length=2, max_length=80)
    merchant: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=2, max_length=1000)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    receipt_reference: str | None = Field(default=None, max_length=500)
    project_reference: str | None = Field(default=None, max_length=160)
    expected_version: int = Field(ge=1)

class TimesheetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_start: date
    period_end: date
    entries: list[TimeEntryCreate] = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if any(e.work_date < self.period_start or e.work_date > self.period_end for e in self.entries):
            raise ValueError("every entry date must be inside the timesheet period")
        return self

class PolicyRuleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: str = Field(min_length=3, max_length=3)
    max_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    receipt_required_above: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    on_violation: Literal["flag", "block"] = "flag"

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value):
        value = value.upper()
        if not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value
