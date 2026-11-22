import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class PurchaseOrder(Base):
    __tablename__ = "ap_purchase_orders"
    __table_args__ = (UniqueConstraint("organization_id", "po_number", name="uq_ap_po_org_number"),
                      Index("ix_ap_po_org_status", "organization_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    po_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("ap_suppliers.id"), nullable=False)
    purchase_request_id: Mapped[str | None] = mapped_column(ForeignKey("ap_purchase_requests.id"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(cascade="all, delete-orphan", order_by="PurchaseOrderLine.id")


class PurchaseOrderLine(Base):
    __tablename__ = "ap_purchase_order_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("ap_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))


class GoodsReceipt(Base):
    __tablename__ = "ap_goods_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("ap_purchase_orders.id"), nullable=False, index=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(String(1000))
    received_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(cascade="all, delete-orphan", order_by="GoodsReceiptLine.id")


class GoodsReceiptLine(Base):
    __tablename__ = "ap_goods_receipt_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    goods_receipt_id: Mapped[str] = mapped_column(ForeignKey("ap_goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    po_line_id: Mapped[str] = mapped_column(ForeignKey("ap_purchase_order_lines.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)


class SupplierInvoice(Base):
    __tablename__ = "ap_supplier_invoices"
    __table_args__ = (UniqueConstraint("organization_id", "supplier_id", "invoice_number", name="uq_ap_invoice_supplier_number"),
                      Index("ix_ap_invoice_org_status_due", "organization_id", "status", "due_date"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("ap_suppliers.id"), nullable=False)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("ap_purchase_orders.id"))
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Captured")
    match_result: Mapped[dict | None] = mapped_column(JSON)
    captured_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentBatch(Base):
    __tablename__ = "ap_payment_batches"
    __table_args__ = (Index("ix_ap_batch_org_status", "organization_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[str | None] = mapped_column(String(128))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_reference: Mapped[str | None] = mapped_column(String(160))
    items: Mapped[list["PaymentBatchItem"]] = relationship(cascade="all, delete-orphan", order_by="PaymentBatchItem.id")


class PaymentBatchItem(Base):
    __tablename__ = "ap_payment_batch_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ap_payment_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("ap_supplier_invoices.id"), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
