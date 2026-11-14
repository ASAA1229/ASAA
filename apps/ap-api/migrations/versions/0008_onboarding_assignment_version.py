"""Snapshot onboarding template versions on assignments."""

from alembic import op
import sqlalchemy as sa

revision = "0008_onboarding_assignment_version"
down_revision = "0007_offboarding_checklists"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "onboarding_assignments",
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("onboarding_assignments", "template_version")
