import re
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ARCustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_code: str | None = Field(default=None, min_length=1, max_length=64)
    legal_name: str = Field(min_length=2, max_length=240)
    trading_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    billing_address: dict | None = None

    @field_validator("legal_name", "trading_name")
    @classmethod
    def trim_names(cls, value):
        return value.strip() if value else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Invalid email address")
        return value.strip().casefold() if value else value


class ARCustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    customer_code: str | None
    legal_name: str
    trading_name: str | None
    email: str | None
    phone: str | None
    billing_address: dict | None
    status: str
    created_at: datetime
    created_by: str


class ARInvoiceLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2)


class ARInvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str
    invoice_number: str | None = Field(default=None, min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=3)
    issue_date: date
    due_date: date
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[ARInvoiceLineInput] = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value):
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a three-letter code")
        return value

    @model_validator(mode="after")
    def dates_valid(self):
        if self.due_date < self.issue_date:
            raise ValueError("Due date cannot precede issue date")
        return self


class ARInvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_amount: Decimal
    line_total: Decimal


class ARInvoiceRead(BaseModel):
    id: str
    organization_id: str
    customer_id: str
    invoice_number: str | None
    currency: str
    issue_date: date
    due_date: date
    status: str
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    notes: str | None
    version: int
    created_at: datetime
    created_by: str
    lines: list[ARInvoiceLineRead]


class ARInvoiceIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class ARAllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class ARReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str
    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    received_date: date
    reference: str | None = Field(default=None, max_length=160)
    method: str | None = Field(default=None, max_length=40)
    allocations: list[ARAllocationInput] = Field(default_factory=list, max_length=100)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value):
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a three-letter code")
        return value

    @model_validator(mode="after")
    def allocation_total_valid(self):
        if sum((a.amount for a in self.allocations), Decimal("0")) > self.amount:
            raise ValueError("Receipt allocations cannot exceed receipt amount")
        if len({a.invoice_id for a in self.allocations}) != len(self.allocations):
            raise ValueError("An invoice may only appear once in a receipt allocation")
        return self


class ARReceiptRead(BaseModel):
    id: str
    organization_id: str
    customer_id: str
    currency: str
    amount: Decimal
    received_date: date
    reference: str | None
    method: str | None
    status: str
    applied_amount: Decimal
    unapplied_amount: Decimal
    created_at: datetime
    created_by: str


class ARInvoiceUpdate(BaseModel):
    """Replace a draft invoice's editable fields using optimistic concurrency."""
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    issue_date: date
    due_date: date
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[ARInvoiceLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def dates_valid(self):
        if self.due_date < self.issue_date:
            raise ValueError("Due date cannot precede issue date")
        return self


class ARReceiptReallocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
