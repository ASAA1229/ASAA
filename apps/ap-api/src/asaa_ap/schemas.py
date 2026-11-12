import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


SupplierStatus = Literal["Draft", "Pending Verification", "Active", "On Hold", "Suspended", "Archived"]


class Address(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, max_length=80)
    lines: list[str] = Field(default_factory=list, max_length=8)
    locality: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_code: str | None = Field(default=None, min_length=1, max_length=64)
    legal_name: str = Field(min_length=2, max_length=240)
    trading_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    website: HttpUrl | None = None
    category: str | None = Field(default=None, max_length=120)
    registration_reference: str | None = Field(default=None, max_length=160)
    addresses: list[Address] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Invalid email address")
        return value.strip().casefold() if value else value

    @field_validator("legal_name")
    @classmethod
    def require_legal_name(cls, value):
        if value is None or not value.strip():
            raise ValueError("Legal name cannot be blank")
        return value.strip()

    @field_validator("legal_name", "trading_name")
    @classmethod
    def trim_names(cls, value):
        return value.strip() if value else value


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    supplier_code: str | None = Field(default=None, min_length=1, max_length=64)
    legal_name: str | None = Field(default=None, min_length=2, max_length=240)
    trading_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    website: HttpUrl | None = None
    category: str | None = Field(default=None, max_length=120)
    registration_reference: str | None = Field(default=None, max_length=160)
    addresses: list[Address] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Invalid email address")
        return value.strip().casefold() if value else value

    @field_validator("legal_name", "trading_name")
    @classmethod
    def trim_names(cls, value):
        return value.strip() if value else value


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    status: SupplierStatus
    reason: str = Field(min_length=3, max_length=1000)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    supplier_code: str | None
    legal_name: str
    trading_name: str | None
    email: str | None
    phone: str | None
    website: str | None
    category: str | None
    registration_reference: str | None
    addresses: list | None
    notes: str | None
    status: SupplierStatus
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    outcome: str
    details: dict
    correlation_id: str | None
    created_at: datetime
