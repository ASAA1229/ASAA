"""Add governed HR operations and payroll review workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0005_people_workflows"
down_revision = "0004_onboarding_task_description"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("onboarding_tasks", sa.Column("assigned_to", sa.String(128), nullable=True))
    op.add_column("onboarding_tasks", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("pay_compensation_records", sa.Column("approved_by", sa.String(128), nullable=True))
    op.add_column("pay_compensation_records", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pay_compensation_records", sa.Column("approval_note", sa.Text(), nullable=True))

    op.add_column("payroll_runs", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payroll_runs", sa.Column("approved_by", sa.String(128), nullable=True))
    op.add_column("payroll_runs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payroll_runs", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("payroll_runs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "hr_employee_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("storage_reference", sa.String(500), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("issued_on", sa.Date()),
        sa.Column("expires_on", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_hr_employee_documents_organization_id", "hr_employee_documents", ["organization_id"])
    op.create_index("ix_hr_document_org_employee", "hr_employee_documents", ["organization_id", "employee_id"])

    op.create_table(
        "hr_employee_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("asset_reference", sa.String(128), nullable=False),
        sa.Column("asset_type", sa.String(64), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date()),
        sa.Column("condition_on_issue", sa.String(64)),
        sa.Column("condition_on_return", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_hr_employee_assets_organization_id", "hr_employee_assets", ["organization_id"])
    op.create_index("ix_hr_asset_org_employee", "hr_employee_assets", ["organization_id", "employee_id"])

    op.create_table(
        "hr_leave_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("leave_category", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reviewer_subject", sa.String(128)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_hr_leave_requests_organization_id", "hr_leave_requests", ["organization_id"])
    op.create_index("ix_hr_leave_org_employee_dates", "hr_leave_requests", ["organization_id", "employee_id", "start_date", "end_date"])

    op.create_table(
        "hr_employee_exit_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("planned_last_day", sa.Date(), nullable=False),
        sa.Column("reason_category", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_hr_employee_exit_cases_organization_id", "hr_employee_exit_cases", ["organization_id"])
    op.create_index("ix_hr_exit_org_employee", "hr_employee_exit_cases", ["organization_id", "employee_id"])


def downgrade():
    op.drop_index("ix_hr_exit_org_employee", table_name="hr_employee_exit_cases")
    op.drop_index("ix_hr_employee_exit_cases_organization_id", table_name="hr_employee_exit_cases")
    op.drop_table("hr_employee_exit_cases")
    op.drop_index("ix_hr_leave_org_employee_dates", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_requests_organization_id", table_name="hr_leave_requests")
    op.drop_table("hr_leave_requests")
    op.drop_index("ix_hr_asset_org_employee", table_name="hr_employee_assets")
    op.drop_index("ix_hr_employee_assets_organization_id", table_name="hr_employee_assets")
    op.drop_table("hr_employee_assets")
    op.drop_index("ix_hr_document_org_employee", table_name="hr_employee_documents")
    op.drop_index("ix_hr_employee_documents_organization_id", table_name="hr_employee_documents")
    op.drop_table("hr_employee_documents")

    for column in ("closed_at", "review_note", "approved_at", "approved_by", "submitted_at"):
        op.drop_column("payroll_runs", column)
    for column in ("approval_note", "approved_at", "approved_by"):
        op.drop_column("pay_compensation_records", column)
    op.drop_column("onboarding_tasks", "assigned_at")
    op.drop_column("onboarding_tasks", "assigned_to")
