"""Additive: owner-entered payroll rule sets (maker-checker) and calculated payroll entry lines with source lineage."""
from alembic import op
import sqlalchemy as sa

revision = "0028_payroll_rule_sets"
down_revision = "0027_payroll_entry_source_references"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payroll_rule_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, index=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("rounding_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approval_note", sa.Text()),
        sa.UniqueConstraint("organization_id", "code", name="uq_payroll_rule_set_org_code"),
    )
    op.create_table(
        "payroll_rule_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, index=True),
        sa.Column("rule_set_id", sa.String(36), sa.ForeignKey("payroll_rule_sets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("basis", sa.String(16), nullable=False),
        sa.Column("rate", sa.Numeric(9, 6)),
        sa.Column("fixed_amount", sa.Numeric(18, 2)),
        sa.Column("cap_amount", sa.Numeric(18, 2)),
        sa.Column("borne_by", sa.String(16), nullable=False),
    )
    op.create_table(
        "payroll_entry_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, index=True),
        sa.Column("entry_id", sa.String(36), sa.ForeignKey("payroll_entries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("rule_set_id", sa.String(36), nullable=False),
        sa.Column("rule_line_id", sa.String(36), nullable=False),
        sa.Column("line_type", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("borne_by", sa.String(16), nullable=False),
        sa.Column("basis_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("rate", sa.Numeric(9, 6)),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("rounding_mode", sa.String(16), nullable=False),
        sa.Column("source_references", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )


def downgrade():
    op.drop_table("payroll_entry_lines")
    op.drop_table("payroll_rule_lines")
    op.drop_table("payroll_rule_sets")
