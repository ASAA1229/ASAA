"""Attendance, shifts, rosters, holidays, attendance policy and corrections."""
from alembic import op
import sqlalchemy as sa

revision = "0024_attendance_shifts"
down_revision = "0023_payables_purchase_to_pay"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "att_shifts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False),
        sa.Column("work_arrangement", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_att_shift_org_code"),
    )
    op.create_index("ix_att_shifts_organization_id", "att_shifts", ["organization_id"])
    op.create_table(
        "att_roster_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("shift_id", sa.String(36), sa.ForeignKey("att_shifts.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("organization_id", "employee_id", "work_date", name="uq_att_roster_employee_date"),
    )
    op.create_index("ix_att_roster_assignments_organization_id", "att_roster_assignments", ["organization_id"])
    op.create_index("ix_att_roster_org_date", "att_roster_assignments", ["organization_id", "work_date"])
    op.create_table(
        "att_holidays",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("optional", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "holiday_date", "name", name="uq_att_holiday_org_date_name"),
    )
    op.create_index("ix_att_holidays_organization_id", "att_holidays", ["organization_id"])
    op.create_table(
        "att_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, unique=True),
        sa.Column("overtime_threshold_minutes", sa.Integer()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128)),
        sa.Column("approved_at", TS),
    )
    op.create_table(
        "att_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("clock_in", TS, nullable=False),
        sa.Column("clock_out", TS),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("worked_minutes", sa.Integer()),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False),
        sa.Column("overtime_status", sa.String(16), nullable=False),
        sa.Column("overtime_reviewed_by", sa.String(128)),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_att_records_organization_id", "att_records", ["organization_id"])
    op.create_index("ix_att_record_org_employee_date", "att_records", ["organization_id", "employee_id", "work_date"])
    op.create_table(
        "att_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("att_records.id")),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("requested_clock_in", TS, nullable=False),
        sa.Column("requested_clock_out", TS, nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", TS),
        sa.Column("review_reason", sa.String(1000)),
    )
    op.create_index("ix_att_corrections_organization_id", "att_corrections", ["organization_id"])
    op.create_index("ix_att_correction_org_status", "att_corrections", ["organization_id", "status"])


def downgrade():
    for table in ("att_corrections", "att_records", "att_policies", "att_holidays", "att_roster_assignments", "att_shifts"):
        op.drop_table(table)
