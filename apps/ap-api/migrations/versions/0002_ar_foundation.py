"""Add Accounts Receivable customers, invoices, receipts and allocations."""
from alembic import op
import sqlalchemy as sa

revision = "0002_ar_foundation"
down_revision = "0001_supplier_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ar_customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("customer_code", sa.String(64)),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("trading_name", sa.String(240)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(64)),
        sa.Column("billing_address", sa.JSON()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "customer_code", name="uq_ar_customer_org_code"),
    )
    op.create_index("ix_ar_customers_organization_id", "ar_customers", ["organization_id"])
    op.create_index("ix_ar_customer_org_name", "ar_customers", ["organization_id", "legal_name"])
    op.create_table(
        "ar_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("ar_customers.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_ar_invoice_org_number"),
    )
    op.create_index("ix_ar_invoices_organization_id", "ar_invoices", ["organization_id"])
    op.create_index("ix_ar_invoice_org_customer", "ar_invoices", ["organization_id", "customer_id"])
    op.create_index("ix_ar_invoice_org_status_due", "ar_invoices", ["organization_id", "status", "due_date"])
    op.create_table(
        "ar_invoice_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
    )
    op.create_index("ix_ar_invoice_lines_invoice_id", "ar_invoice_lines", ["invoice_id"])
    op.create_table(
        "ar_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("ar_customers.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(160)),
        sa.Column("method", sa.String(40)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_ar_receipts_organization_id", "ar_receipts", ["organization_id"])
    op.create_table(
        "ar_receipt_allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("receipt_id", sa.String(36), sa.ForeignKey("ar_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("receipt_id", "invoice_id", name="uq_ar_receipt_invoice_allocation"),
    )
    op.create_index("ix_ar_receipt_allocations_receipt_id", "ar_receipt_allocations", ["receipt_id"])
    op.create_index("ix_ar_receipt_allocations_invoice_id", "ar_receipt_allocations", ["invoice_id"])


def downgrade():
    op.drop_index("ix_ar_receipt_allocations_invoice_id", table_name="ar_receipt_allocations")
    op.drop_index("ix_ar_receipt_allocations_receipt_id", table_name="ar_receipt_allocations")
    op.drop_table("ar_receipt_allocations")
    op.drop_index("ix_ar_receipts_organization_id", table_name="ar_receipts")
    op.drop_table("ar_receipts")
    op.drop_index("ix_ar_invoice_lines_invoice_id", table_name="ar_invoice_lines")
    op.drop_table("ar_invoice_lines")
    op.drop_index("ix_ar_invoice_org_status_due", table_name="ar_invoices")
    op.drop_index("ix_ar_invoice_org_customer", table_name="ar_invoices")
    op.drop_index("ix_ar_invoices_organization_id", table_name="ar_invoices")
    op.drop_table("ar_invoices")
    op.drop_index("ix_ar_customer_org_name", table_name="ar_customers")
    op.drop_index("ix_ar_customers_organization_id", table_name="ar_customers")
    op.drop_table("ar_customers")
