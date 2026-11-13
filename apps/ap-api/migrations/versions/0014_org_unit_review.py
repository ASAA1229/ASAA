"""Add independent review evidence to organization units."""
from alembic import op
import sqlalchemy as sa

revision = "0014_org_unit_review"
down_revision = "0013_org_access_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organization_units", sa.Column("reviewed_by", sa.String(128), nullable=True))
    op.add_column("organization_units", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organization_units", sa.Column("review_reason", sa.String(1000), nullable=True))


def downgrade():
    op.drop_column("organization_units", "review_reason")
    op.drop_column("organization_units", "reviewed_at")
    op.drop_column("organization_units", "reviewed_by")
