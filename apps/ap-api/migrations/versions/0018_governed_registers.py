"""Governed registers: versioned, reviewed records for policies, risks, controls, obligations, contracts and more."""
from alembic import op
import sqlalchemy as sa

revision = "0018_governed_registers"
down_revision = "0017_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "governed_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("register_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("owner_subject", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("review_due", sa.Date()),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("submitted_by", sa.String(128)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_reason", sa.String(1000)),
        sa.UniqueConstraint("organization_id", "register_type", "code", "revision", name="uq_governed_record_revision"),
    )
    op.create_index("ix_governed_records_organization_id", "governed_records", ["organization_id"])
    op.create_index("ix_governed_record_list", "governed_records", ["organization_id", "register_type", "status"])


def downgrade():
    op.drop_table("governed_records")
