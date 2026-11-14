"""Version onboarding templates."""

from alembic import op
import sqlalchemy as sa

revision = "0006_onboarding_template_version"
down_revision = "0005_people_workflows"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "onboarding_templates",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("onboarding_templates", "version")
