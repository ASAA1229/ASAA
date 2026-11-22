"""Purchase orders, goods receipts, supplier invoices and payment batches."""
from alembic import op
import sqlalchemy as sa

revision = "0023_payables_purchase_to_pay"
down_revision = "0022_identity_adoption_requests"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "ap_purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("po_number", sa.String(64), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("ap_suppliers.id"), nullable=False),
        sa.Column("purchase_request_id", sa.String(36), sa.ForeignKey("ap_purchase_requests.id")),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", TS),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("issued_at", TS),
        sa.UniqueConstraint("organization_id", "po_number", name="uq_ap_po_org_number"),
    )
    op.create_index("ix_ap_purchase_orders_organization_id", "ap_purchase_orders", ["organization_id"])
    op.create_index("ix_ap_po_org_status", "ap_purchase_orders", ["organization_id", "status"])
    op.create_table(
        "ap_purchase_order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("ap_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(40), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("received_quantity", sa.Numeric(12, 3), nullable=False),
    )
    op.create_index("ix_ap_purchase_order_lines_purchase_order_id", "ap_purchase_order_lines", ["purchase_order_id"])
    op.create_table(
        "ap_goods_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("ap_purchase_orders.id"), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(160)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("received_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_ap_goods_receipts_organization_id", "ap_goods_receipts", ["organization_id"])
    op.create_index("ix_ap_goods_receipts_purchase_order_id", "ap_goods_receipts", ["purchase_order_id"])
    op.create_table(
        "ap_goods_receipt_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("goods_receipt_id", sa.String(36), sa.ForeignKey("ap_goods_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("po_line_id", sa.String(36), sa.ForeignKey("ap_purchase_order_lines.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
    )
    op.create_index("ix_ap_goods_receipt_lines_goods_receipt_id", "ap_goods_receipt_lines", ["goods_receipt_id"])
    op.create_table(
        "ap_supplier_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("ap_suppliers.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("ap_purchase_orders.id")),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("tax_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("match_result", sa.JSON()),
        sa.Column("captured_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", TS),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("paid_at", TS),
        sa.UniqueConstraint("organization_id", "supplier_id", "invoice_number", name="uq_ap_invoice_supplier_number"),
    )
    op.create_index("ix_ap_supplier_invoices_organization_id", "ap_supplier_invoices", ["organization_id"])
    op.create_index("ix_ap_invoice_org_status_due", "ap_supplier_invoices", ["organization_id", "status", "due_date"])
    op.create_table(
        "ap_payment_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", TS),
        sa.Column("paid_by", sa.String(128)),
        sa.Column("paid_at", TS),
        sa.Column("payment_reference", sa.String(160)),
    )
    op.create_index("ix_ap_payment_batches_organization_id", "ap_payment_batches", ["organization_id"])
    op.create_index("ix_ap_batch_org_status", "ap_payment_batches", ["organization_id", "status"])
    op.create_table(
        "ap_payment_batch_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("ap_payment_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ap_supplier_invoices.id"), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
    )
    op.create_index("ix_ap_payment_batch_items_batch_id", "ap_payment_batch_items", ["batch_id"])


def downgrade():
    for table in ("ap_payment_batch_items", "ap_payment_batches", "ap_supplier_invoices", "ap_goods_receipt_lines", "ap_goods_receipts",
                  "ap_purchase_order_lines", "ap_purchase_orders"):
        op.drop_table(table)
