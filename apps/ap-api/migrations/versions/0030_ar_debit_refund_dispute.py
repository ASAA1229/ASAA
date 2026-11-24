"""Additive: AR debit notes, receipt refunds and invoice disputes (all traceable to invoices/receipts, maker-checker where money moves)."""
from alembic import op
import sqlalchemy as sa

revision = "0030_ar_debit_refund_dispute"
down_revision = "0029_leave_policy_counting_accrual"
branch_labels = None
depends_on = None


def _common():
    return [sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(128), nullable=False, index=True),
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("ar_customers.id"), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(128), nullable=False)]


def upgrade():
    op.create_table(
        "ar_debit_notes", *_common(),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reviewed_by", sa.String(128)), sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("review_reason", sa.String(500)))
    op.create_index("ix_ar_debit_note_org_invoice", "ar_debit_notes", ["organization_id", "invoice_id"])
    op.create_index("ix_ar_debit_note_org_status", "ar_debit_notes", ["organization_id", "status"])
    op.create_table(
        "ar_refunds", *_common(),
        sa.Column("receipt_id", sa.String(36), sa.ForeignKey("ar_receipts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reviewed_by", sa.String(128)), sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("review_reason", sa.String(500)),
        sa.Column("refunded_by", sa.String(128)), sa.Column("refunded_at", sa.DateTime(timezone=True)), sa.Column("payment_reference", sa.String(200)))
    op.create_index("ix_ar_refund_org_receipt", "ar_refunds", ["organization_id", "receipt_id"])
    op.create_index("ix_ar_refund_org_status", "ar_refunds", ["organization_id", "status"])
    op.create_table(
        "ar_disputes", *_common(),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id"), nullable=False),
        sa.Column("disputed_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("resolved_by", sa.String(128)), sa.Column("resolved_at", sa.DateTime(timezone=True)), sa.Column("resolution_note", sa.String(500)),
        sa.Column("credit_note_id", sa.String(36), sa.ForeignKey("ar_credit_notes.id")))
    op.create_index("ix_ar_dispute_org_invoice", "ar_disputes", ["organization_id", "invoice_id"])
    op.create_index("ix_ar_dispute_org_status", "ar_disputes", ["organization_id", "status"])


def downgrade():
    op.drop_table("ar_disputes")
    op.drop_table("ar_refunds")
    op.drop_table("ar_debit_notes")
