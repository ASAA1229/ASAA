"""Additive: owner-chosen leave day counting (weekends, holidays) and accrual mode on leave policies."""
from alembic import op
import sqlalchemy as sa

revision = "0029_leave_policy_counting_accrual"
down_revision = "0028_payroll_rule_sets"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hr_leave_policies", sa.Column("count_mode", sa.String(12), nullable=False, server_default="calendar"))
    op.add_column("hr_leave_policies", sa.Column("weekend_days", sa.JSON()))
    op.add_column("hr_leave_policies", sa.Column("exclude_holidays", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("hr_leave_policies", sa.Column("accrual_mode", sa.String(12), nullable=False, server_default="annual"))


def downgrade():
    for column in ("accrual_mode", "exclude_holidays", "weekend_days", "count_mode"):
        op.drop_column("hr_leave_policies", column)
