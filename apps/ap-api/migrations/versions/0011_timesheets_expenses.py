"""Add timesheet and expense claim foundations."""
from alembic import op
import sqlalchemy as sa

revision = "0011_timesheets_expenses"
down_revision = "0010_authority_register"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("work_timesheets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_subject", sa.String(128), nullable=False),
        sa.Column("employee_reference", sa.String(128)),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("total_hours", sa.Numeric(9, 2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)))
    op.create_index("ix_work_timesheets_organization_id", "work_timesheets", ["organization_id"])
    op.create_index("ix_work_timesheet_org_employee_period", "work_timesheets",
                    ["organization_id", "employee_subject", "period_start", "period_end"])
    op.create_table("work_time_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("timesheet_id", sa.String(36), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("project_reference", sa.String(160)),
        sa.Column("task_reference", sa.String(160)),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("hours", sa.Numeric(7, 2), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False))
    op.create_index("ix_work_time_entries_organization_id", "work_time_entries", ["organization_id"])
    op.create_index("ix_work_time_entries_timesheet_id", "work_time_entries", ["timesheet_id"])
    op.create_table("expense_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_subject", sa.String(128), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category_code", sa.String(80), nullable=False),
        sa.Column("merchant", sa.String(200)),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("receipt_reference", sa.String(500)),
        sa.Column("project_reference", sa.String(160)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("reimbursed_at", sa.DateTime(timezone=True)),
        sa.Column("reimbursed_by", sa.String(128)),
        sa.Column("reimbursement_reference", sa.String(200)))
    op.create_index("ix_expense_claims_organization_id", "expense_claims", ["organization_id"])
    op.create_index("ix_expense_claim_org_employee_status", "expense_claims",
                    ["organization_id", "employee_subject", "status"])

def downgrade():
    op.drop_index("ix_expense_claim_org_employee_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_organization_id", table_name="expense_claims")
    op.drop_table("expense_claims")
    op.drop_index("ix_work_time_entries_timesheet_id", table_name="work_time_entries")
    op.drop_index("ix_work_time_entries_organization_id", table_name="work_time_entries")
    op.drop_table("work_time_entries")
    op.drop_index("ix_work_timesheet_org_employee_period", table_name="work_timesheets")
    op.drop_index("ix_work_timesheets_organization_id", table_name="work_timesheets")
    op.drop_table("work_timesheets")
