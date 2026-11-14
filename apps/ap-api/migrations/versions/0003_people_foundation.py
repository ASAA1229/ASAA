"""Add HR, onboarding and payroll foundation tables."""
from alembic import op
import sqlalchemy as sa

revision = "0003_people_foundation"
down_revision = "0002_ar_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_code", sa.String(64)),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False),
        sa.Column("preferred_name", sa.String(120)),
        sa.Column("work_email", sa.String(320)),
        sa.Column("work_phone", sa.String(64)),
        sa.Column("employment_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("hire_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("organization_id", "employee_code", name="uq_hr_employee_org_code"),
    )
    op.create_index("ix_hr_employees_organization_id", "hr_employees", ["organization_id"])
    op.create_index("ix_hr_employee_org_name", "hr_employees", ["organization_id", "last_name", "first_name"])
    op.create_index("ix_hr_employee_org_status", "hr_employees", ["organization_id", "status"])

    op.create_table(
        "hr_employment_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("department_id", sa.String(128)),
        sa.Column("position_title", sa.String(160)),
        sa.Column("manager_employee_id", sa.String(36), sa.ForeignKey("hr_employees.id")),
        sa.Column("work_location", sa.String(160)),
        sa.Column("employment_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_hr_employment_records_organization_id", "hr_employment_records", ["organization_id"])
    op.create_index("ix_hr_employment_org_employee_effective", "hr_employment_records", ["organization_id", "employee_id", "effective_from"])

    op.create_table(
        "onboarding_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("template_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("employment_type", sa.String(40)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "template_code", name="uq_onboarding_template_org_code"),
    )
    op.create_index("ix_onboarding_templates_organization_id", "onboarding_templates", ["organization_id"])

    op.create_table(
        "onboarding_task_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_role", sa.String(64), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
    )
    op.create_index("ix_onboarding_task_templates_template_id", "onboarding_task_templates", ["template_id"])

    op.create_table(
        "onboarding_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("onboarding_templates.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("target_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "employee_id", "template_id", name="uq_onboarding_assignment_employee_template"),
    )
    op.create_index("ix_onboarding_assignments_organization_id", "onboarding_assignments", ["organization_id"])
    op.create_index("ix_onboarding_assignments_employee_id", "onboarding_assignments", ["employee_id"])

    op.create_table(
        "onboarding_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("onboarding_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_task_id", sa.String(36)),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("owner_role", sa.String(64), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by", sa.String(128)),
        sa.Column("evidence_reference", sa.String(500)),
        sa.UniqueConstraint("assignment_id", "source_task_id", name="uq_onboarding_assignment_source_task"),
    )
    op.create_index("ix_onboarding_tasks_organization_id", "onboarding_tasks", ["organization_id"])
    op.create_index("ix_onboarding_tasks_assignment_id", "onboarding_tasks", ["assignment_id"])

    op.create_table(
        "pay_compensation_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("pay_basis", sa.String(32), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("frequency", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_pay_compensation_records_organization_id", "pay_compensation_records", ["organization_id"])
    op.create_index("ix_pay_compensation_records_employee_id", "pay_compensation_records", ["employee_id"])
    op.create_index("ix_pay_comp_org_employee_effective", "pay_compensation_records", ["organization_id", "employee_id", "effective_from"])

    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("period_code", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "period_code", name="uq_pay_period_org_code"),
    )
    op.create_index("ix_payroll_periods_organization_id", "payroll_periods", ["organization_id"])

    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("period_id", sa.String(36), sa.ForeignKey("payroll_periods.id"), nullable=False),
        sa.Column("run_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "run_code", name="uq_pay_run_org_code"),
    )
    op.create_index("ix_payroll_runs_organization_id", "payroll_runs", ["organization_id"])
    op.create_index("ix_payroll_runs_period_id", "payroll_runs", ["period_id"])

    op.create_table(
        "payroll_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("deduction_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "run_id", "employee_id", name="uq_pay_entry_org_run_employee"),
    )
    op.create_index("ix_payroll_entries_organization_id", "payroll_entries", ["organization_id"])
    op.create_index("ix_payroll_entries_run_id", "payroll_entries", ["run_id"])
    op.create_index("ix_payroll_entries_employee_id", "payroll_entries", ["employee_id"])


def downgrade():
    for index, table in [
        ("ix_payroll_entries_employee_id", "payroll_entries"),
        ("ix_payroll_entries_run_id", "payroll_entries"),
        ("ix_payroll_entries_organization_id", "payroll_entries"),
    ]:
        op.drop_index(index, table_name=table)
    op.drop_table("payroll_entries")
    op.drop_index("ix_payroll_runs_period_id", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_organization_id", table_name="payroll_runs")
    op.drop_table("payroll_runs")
    op.drop_index("ix_payroll_periods_organization_id", table_name="payroll_periods")
    op.drop_table("payroll_periods")
    op.drop_index("ix_pay_comp_org_employee_effective", table_name="pay_compensation_records")
    op.drop_index("ix_pay_compensation_records_employee_id", table_name="pay_compensation_records")
    op.drop_index("ix_pay_compensation_records_organization_id", table_name="pay_compensation_records")
    op.drop_table("pay_compensation_records")
    op.drop_index("ix_onboarding_tasks_assignment_id", table_name="onboarding_tasks")
    op.drop_index("ix_onboarding_tasks_organization_id", table_name="onboarding_tasks")
    op.drop_table("onboarding_tasks")
    op.drop_index("ix_onboarding_assignments_employee_id", table_name="onboarding_assignments")
    op.drop_index("ix_onboarding_assignments_organization_id", table_name="onboarding_assignments")
    op.drop_table("onboarding_assignments")
    op.drop_index("ix_onboarding_task_templates_template_id", table_name="onboarding_task_templates")
    op.drop_table("onboarding_task_templates")
    op.drop_index("ix_onboarding_templates_organization_id", table_name="onboarding_templates")
    op.drop_table("onboarding_templates")
    op.drop_index("ix_hr_employment_org_employee_effective", table_name="hr_employment_records")
    op.drop_index("ix_hr_employment_records_organization_id", table_name="hr_employment_records")
    op.drop_table("hr_employment_records")
    op.drop_index("ix_hr_employee_org_status", table_name="hr_employees")
    op.drop_index("ix_hr_employee_org_name", table_name="hr_employees")
    op.drop_index("ix_hr_employees_organization_id", table_name="hr_employees")
    op.drop_table("hr_employees")
