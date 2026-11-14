import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PurchaseRequestLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=2, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_of_measure: str = Field(min_length=1, max_length=40)
    estimated_unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

    @field_validator("description", "unit_of_measure")
    @classmethod
    def trim_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class PurchaseRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    purpose: str = Field(min_length=5, max_length=4000)
    needed_by: date
    currency: str = Field(min_length=3, max_length=3)
    cost_center: str | None = Field(default=None, max_length=120)
    project_reference: str | None = Field(default=None, max_length=160)
    lines: list[PurchaseRequestLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("title", "purpose", "currency")
    @classmethod
    def trim_required(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str):
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a three-letter ISO-style code")
        return value

    @model_validator(mode="after")
    def validate_request_totals(self):
        if self.needed_by < date.today():
            raise ValueError("needed_by cannot be in the past")
        estimated_total = sum((line.quantity * line.estimated_unit_cost for line in self.lines), Decimal("0"))
        if estimated_total > Decimal("9999999999999999.99"):
            raise ValueError("Estimated total exceeds the supported monetary precision")
        return self


class PurchaseRequestSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class PurchaseRequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject", "return"]
    reason: str = Field(min_length=3, max_length=1000)


class PurchaseRequestLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    description: str
    quantity: Decimal
    unit_of_measure: str
    estimated_unit_cost: Decimal
    estimated_line_total: Decimal


class PurchaseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    title: str
    purpose: str
    needed_by: date
    currency: str
    cost_center: str | None
    project_reference: str | None
    estimated_total: Decimal
    status: str
    requested_by: str
    created_by: str
    created_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_reason: str | None
    version: int
    lines: list[PurchaseRequestLineRead]
