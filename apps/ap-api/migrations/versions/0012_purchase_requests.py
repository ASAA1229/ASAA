"""Add purchase request and line tables."""
from alembic import op
import sqlalchemy as sa

revision = "0012_purchase_requests"
down_revision = "0011_timesheets_expenses"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ap_purchase_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("needed_by", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cost_center", sa.String(120)),
        sa.Column("project_reference", sa.String(160)),
        sa.Column("estimated_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_ap_purchase_requests_organization_id", "ap_purchase_requests", ["organization_id"])
    op.create_index("ix_ap_purchase_request_org_status", "ap_purchase_requests", ["organization_id", "status"])
    op.create_index("ix_ap_purchase_request_org_requester", "ap_purchase_requests", ["organization_id", "requested_by"])
    op.create_table(
        "ap_purchase_request_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_request_id", sa.String(36), sa.ForeignKey("ap_purchase_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(40), nullable=False),
        sa.Column("estimated_unit_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("estimated_line_total", sa.Numeric(18, 2), nullable=False),
    )
    op.create_index("ix_ap_purchase_request_lines_request_id", "ap_purchase_request_lines", ["purchase_request_id"])


def downgrade():
    op.drop_index("ix_ap_purchase_request_lines_request_id", table_name="ap_purchase_request_lines")
    op.drop_table("ap_purchase_request_lines")
    op.drop_index("ix_ap_purchase_request_org_requester", table_name="ap_purchase_requests")
    op.drop_index("ix_ap_purchase_request_org_status", table_name="ap_purchase_requests")
    op.drop_index("ix_ap_purchase_requests_organization_id", table_name="ap_purchase_requests")
    op.drop_table("ap_purchase_requests")
