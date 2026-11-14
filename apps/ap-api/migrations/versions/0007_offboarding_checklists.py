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
    with op.batch_alter_table("hr_employee_exit_cases") as batch_op:
        batch_op.add_column(sa.Column("checklist_assignment_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_hr_exit_checklist_assignment",
            "onboarding_assignments",
            ["checklist_assignment_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("hr_employee_exit_cases") as batch_op:
        batch_op.drop_constraint("fk_hr_exit_checklist_assignment", type_="foreignkey")
        batch_op.drop_column("checklist_assignment_id")
    op.drop_column("onboarding_templates", "workflow_type")
