"""Additive: payroll entries may reference the approved source records they were derived from."""
from alembic import op
import sqlalchemy as sa

revision = "0027_payroll_entry_source_references"
down_revision = "0026_expense_policy_resubmission"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payroll_entries", sa.Column("source_references", sa.JSON()))


def downgrade():
    op.drop_column("payroll_entries", "source_references")
