"""Additive: per-organization authorization scope mode (token | narrow | strict). Scope types Unit and Customer need no schema change
(scope_type and scope_reference are free-width strings validated by the API). No row means the default mode (narrow)."""
from alembic import op
import sqlalchemy as sa

revision = "0031_authorization_scope_mode"
down_revision = "0030_ar_debit_refund_dispute"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authorization_scope_settings",
        sa.Column("organization_id", sa.String(128), primary_key=True),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(1000)),
    )


def downgrade():
    op.drop_table("authorization_scope_settings")
