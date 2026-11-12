"""Create AP supplier and audit foundations."""
from alembic import op
import sqlalchemy as sa

revision = "0001_supplier_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ap_suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("supplier_code", sa.String(64)),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("normalized_legal_name", sa.String(240), nullable=False),
        sa.Column("trading_name", sa.String(240)),
        sa.Column("email", sa.String(320)),
        sa.Column("normalized_email", sa.String(320)),
        sa.Column("phone", sa.String(64)),
        sa.Column("website", sa.String(500)),
        sa.Column("category", sa.String(120)),
        sa.Column("registration_reference", sa.String(160)),
        sa.Column("addresses", sa.JSON()),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "supplier_code", name="uq_ap_supplier_org_code"),
        sa.UniqueConstraint("organization_id", "normalized_legal_name", name="uq_ap_supplier_org_normalized_name"),
    )
    op.create_index("ix_ap_suppliers_organization_id", "ap_suppliers", ["organization_id"])
    op.create_index("ix_ap_supplier_org_name", "ap_suppliers", ["organization_id", "normalized_legal_name"])
    op.create_index("ix_ap_supplier_org_status", "ap_suppliers", ["organization_id", "status"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_org_created", "audit_events", ["organization_id", "created_at"])


def downgrade():
    op.drop_index("ix_audit_org_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_ap_supplier_org_status", table_name="ap_suppliers")
    op.drop_index("ix_ap_supplier_org_name", table_name="ap_suppliers")
    op.drop_index("ix_ap_suppliers_organization_id", table_name="ap_suppliers")
    op.drop_table("ap_suppliers")
