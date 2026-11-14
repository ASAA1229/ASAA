"""Preserve onboarding task descriptions in assignment snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0004_onboarding_task_description"
down_revision = "0003_people_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("onboarding_tasks", sa.Column("description", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("onboarding_tasks", "description")
