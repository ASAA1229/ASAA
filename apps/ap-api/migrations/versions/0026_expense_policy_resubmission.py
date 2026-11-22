"""Configurable expense policy rules and per-claim policy flags."""
from alembic import op
import sqlalchemy as sa

revision = "0026_expense_policy_resubmission"
down_revision = "0025_credit_notes_service_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expense_claims", sa.Column("policy_flags", sa.JSON()))
    op.create_table(
        "expense_policy_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("category_code", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("max_amount", sa.Numeric(18, 2)),
        sa.Column("receipt_required_above", sa.Numeric(18, 2)),
        sa.Column("on_violation", sa.String(8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "category_code", name="uq_expense_policy_org_category"),
    )
    op.create_index("ix_expense_policy_rules_organization_id", "expense_policy_rules", ["organization_id"])


def downgrade():
    op.drop_table("expense_policy_rules")
    op.drop_column("expense_claims", "policy_flags")
