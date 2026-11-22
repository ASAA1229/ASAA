import uuid
from decimal import Decimal
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Supplier(Base):
    __tablename__ = "ap_suppliers"
    __table_args__ = (
        UniqueConstraint("organization_id", "supplier_code", name="uq_ap_supplier_org_code"),
        UniqueConstraint("organization_id", "normalized_legal_name", name="uq_ap_supplier_org_normalized_name"),
        Index("ix_ap_supplier_org_name", "organization_id", "normalized_legal_name"),
        Index("ix_ap_supplier_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    supplier_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(240))
    email: Mapped[str | None] = mapped_column(String(320))
    normalized_email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))
    website: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(120))
    registration_reference: Mapped[str | None] = mapped_column(String(160))
    addresses: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ARCustomer(Base):
    __tablename__ = "ar_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_code", name="uq_ar_customer_org_code"),
        Index("ix_ar_customer_org_name", "organization_id", "legal_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_code: Mapped[str | None] = mapped_column(String(64))
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(240))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))
    billing_address: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class ARInvoice(Base):
    __tablename__ = "ar_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_ar_invoice_org_number"),
        Index("ix_ar_invoice_org_customer", "organization_id", "customer_id"),
        Index("ix_ar_invoice_org_status_due", "organization_id", "status", "due_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("ar_customers.id"), nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class ARInvoiceLine(Base):
    __tablename__ = "ar_invoice_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(ForeignKey("ar_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class ARReceipt(Base):
    __tablename__ = "ar_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("ar_customers.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    method: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Recorded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class ARReceiptAllocation(Base):
    __tablename__ = "ar_receipt_allocations"
    __table_args__ = (UniqueConstraint("receipt_id", "invoice_id", name="uq_ar_receipt_invoice_allocation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    receipt_id: Mapped[str] = mapped_column(ForeignKey("ar_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("ar_invoices.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class ARCreditNote(Base):
    """Credit against an issued invoice. Maker-checker: applied (reduces the invoice balance) only when approved by someone other than its maker."""
    __tablename__ = "ar_credit_notes"
    __table_args__ = (Index("ix_ar_credit_note_org_invoice", "organization_id", "invoice_id"),
                      Index("ix_ar_credit_note_org_status", "organization_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("ar_customers.id"), nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("ar_invoices.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(String(500))
