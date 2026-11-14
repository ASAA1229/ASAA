"""Add organization structure and identity access review foundations."""
from alembic import op
import sqlalchemy as sa

revision = "0013_org_access_admin"
down_revision = "0012_purchase_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("legal_name", sa.String(240)),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("timezone", sa.String(80)),
        sa.Column("website", sa.String(300)),
        sa.Column("registration_reference", sa.String(160)),
        sa.Column("registered_address", sa.JSON()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
    )
    op.create_table(
        "organization_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("organization_units.id")),
        sa.Column("unit_type", sa.String(32), nullable=False),
        sa.Column("unit_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("owner_subject", sa.String(128)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "unit_code", name="uq_org_unit_org_code"),
    )
    op.create_index("ix_organization_units_organization_id", "organization_units", ["organization_id"])
    op.create_index("ix_org_unit_org_parent", "organization_units", ["organization_id", "parent_id"])
    op.create_index("ix_org_unit_org_type_status", "organization_units", ["organization_id", "unit_type", "status"])
    op.create_table(
        "access_review_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source_reference", sa.String(300), nullable=False),
        sa.Column("snapshot_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_access_review_campaigns_organization_id", "access_review_campaigns", ["organization_id"])
    op.create_index("ix_access_review_org_status", "access_review_campaigns", ["organization_id", "status"])
    op.create_table(
        "access_review_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("access_review_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("role_code", sa.String(128)),
        sa.Column("permission_snapshot", sa.JSON(), nullable=False),
        sa.Column("scope_reference", sa.String(300), nullable=False),
        sa.Column("justification", sa.String(1000)),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_access_review_items_organization_id", "access_review_items", ["organization_id"])
    op.create_index("ix_access_review_item_campaign_status", "access_review_items", ["campaign_id", "decision"])


def downgrade():
    op.drop_index("ix_access_review_item_campaign_status", table_name="access_review_items")
    op.drop_index("ix_access_review_items_organization_id", table_name="access_review_items")
    op.drop_table("access_review_items")
    op.drop_index("ix_access_review_org_status", table_name="access_review_campaigns")
    op.drop_index("ix_access_review_campaigns_organization_id", table_name="access_review_campaigns")
    op.drop_table("access_review_campaigns")
    op.drop_index("ix_org_unit_org_type_status", table_name="organization_units")
    op.drop_index("ix_org_unit_org_parent", table_name="organization_units")
    op.drop_index("ix_organization_units_organization_id", table_name="organization_units")
    op.drop_table("organization_units")
    op.drop_table("organization_profiles")
