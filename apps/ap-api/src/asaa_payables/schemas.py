import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _currency(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError("Currency must be a three-letter ISO-style code")
    return value


class POLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=2, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_of_measure: str = Field(min_length=1, max_length=40)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class POCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str = Field(min_length=1, max_length=36)
    purchase_request_id: str | None = Field(default=None, max_length=36)
    currency: str = Field(min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[POLineIn] = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str):
        return _currency(value)


class POLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    line_total: Decimal
    received_quantity: Decimal


class POOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    po_number: str
    supplier_id: str
    purchase_request_id: str | None
    currency: str
    total: Decimal
    status: str
    notes: str | None
    created_by: str
    created_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str | None
    issued_at: datetime | None
    lines: list[POLineOut]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


class ReceiptLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    po_line_id: str = Field(min_length=1, max_length=36)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class ReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_order_id: str = Field(min_length=1, max_length=36)
    received_date: date
    reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=100)


class ReceiptLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    po_line_id: str
    quantity: Decimal


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    purchase_order_id: str
    received_date: date
    reference: str | None
    notes: str | None
    received_by: str
    created_at: datetime
    lines: list[ReceiptLineOut]


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str = Field(min_length=1, max_length=36)
    purchase_order_id: str | None = Field(default=None, max_length=36)
    invoice_number: str = Field(min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=3)
    invoice_date: date
    due_date: date
    tax_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    total: Decimal = Field(gt=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def check_currency(cls, value: str):
        return _currency(value)

    @field_validator("invoice_number")
    @classmethod
    def trim_number(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Invoice number cannot be blank")
        return value


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    supplier_id: str
    purchase_order_id: str | None
    invoice_number: str
    currency: str
    invoice_date: date
    due_date: date
    tax_total: Decimal
    total: Decimal
    status: str
    match_result: dict | None
    captured_by: str
    created_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str | None
    paid_at: datetime | None


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_ids: list[str] = Field(min_length=1, max_length=500)


class BatchPaid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_reference: str = Field(min_length=3, max_length=160)


class BatchItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    invoice_id: str
    amount: Decimal


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    currency: str
    total: Decimal
    status: str
    created_by: str
    created_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    paid_by: str | None
    paid_at: datetime | None
    payment_reference: str | None
    items: list[BatchItemOut]
