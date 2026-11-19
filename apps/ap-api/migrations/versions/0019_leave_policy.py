"""Configurable leave policies (pending owner approval by default)."""
from alembic import op
import sqlalchemy as sa

revision = "0019_leave_policy"
down_revision = "0018_governed_registers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_leave_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("leave_category", sa.String(64), nullable=False),
        sa.Column("annual_entitlement_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("carry_over_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("enforce_balance", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "leave_category", name="uq_leave_policy_org_category"),
    )
    op.create_index("ix_hr_leave_policies_organization_id", "hr_leave_policies", ["organization_id"])


def downgrade():
    op.drop_table("hr_leave_policies")
