"""Ecosystem integration events (envelope id is the idempotency key)."""
from alembic import op
import sqlalchemy as sa

revision = "0020_integration_events"
down_revision = "0019_leave_policy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("type", sa.String(120), nullable=False),
        sa.Column("project", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(200)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("received_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_integration_events_organization_id", "integration_events", ["organization_id"])
    op.create_index("ix_integration_events_source", "integration_events", ["source"])
    op.create_index("ix_integration_events_type", "integration_events", ["type"])
    op.create_index("ix_integration_events_project", "integration_events", ["project"])
    op.create_index("ix_integration_events_org_occurred", "integration_events", ["organization_id", "occurred_at"])


def downgrade():
    op.drop_table("integration_events")
