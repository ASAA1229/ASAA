"""Maker-checker records for adopting pre-existing identity provider accounts."""
from alembic import op
import sqlalchemy as sa

revision = "0022_identity_adoption_requests"
down_revision = "0021_integration_event_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_adoption_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("provider_username", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(500)),
        sa.Column("result", sa.String(300)),
    )
    op.create_index("ix_identity_adoption_requests_organization_id", "identity_adoption_requests", ["organization_id"])
    op.create_index("ix_identity_adoption_org_status", "identity_adoption_requests", ["organization_id", "status"])


def downgrade():
    op.drop_index("ix_identity_adoption_org_status", table_name="identity_adoption_requests")
    op.drop_index("ix_identity_adoption_requests_organization_id", table_name="identity_adoption_requests")
    op.drop_table("identity_adoption_requests")
