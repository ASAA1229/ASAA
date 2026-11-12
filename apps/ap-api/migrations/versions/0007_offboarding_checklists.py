"""Support offboarding checklist templates and exit-case links."""

from alembic import op
import sqlalchemy as sa

revision = "0007_offboarding_checklists"
down_revision = "0006_onboarding_template_version"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "onboarding_templates",
        sa.Column("workflow_type", sa.String(24), nullable=False, server_default="Onboarding"),
    )
    op.add_column(
        "hr_employee_exit_cases",
        sa.Column("checklist_assignment_id", sa.String(36),
                  sa.ForeignKey("onboarding_assignments.id"), nullable=True),
    )


def downgrade():
    op.drop_column("hr_employee_exit_cases", "checklist_assignment_id")
    op.drop_column("onboarding_templates", "workflow_type")
