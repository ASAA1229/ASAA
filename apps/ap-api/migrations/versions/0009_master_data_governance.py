"""Add organization-scoped master-data ownership and provenance registry."""

from alembic import op
import sqlalchemy as sa

revision = "0009_master_data_governance"
down_revision = "0008_onboarding_assignment_version"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "master_data_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("domain_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("authoritative_source", sa.String(160), nullable=False),
        sa.Column("owner_subject", sa.String(128), nullable=False),
        sa.Column("steward_subject", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "domain_code", name="uq_master_data_domain_org_code"),
    )
    op.create_index("ix_master_data_domains_organization_id", "master_data_domains", ["organization_id"])
    op.create_index("ix_master_data_domain_org_status", "master_data_domains", ["organization_id", "status"])

    op.create_table(
        "master_data_record_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("domain_id", sa.String(36), sa.ForeignKey("master_data_domains.id"), nullable=False),
        sa.Column("record_type", sa.String(80), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("source_system", sa.String(120), nullable=False),
        sa.Column("source_record_id", sa.String(160), nullable=False),
        sa.Column("match_key_fingerprint", sa.String(128)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("canonical_record_id", sa.String(36), sa.ForeignKey("master_data_record_references.id")),
        sa.Column("supersession_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "domain_id", "record_type", "record_id",
                            name="uq_master_data_record_identity"),
        sa.UniqueConstraint("organization_id", "domain_id", "source_system", "source_record_id",
                            name="uq_master_data_source_identity"),
    )
    op.create_index("ix_master_data_record_references_organization_id", "master_data_record_references", ["organization_id"])
    op.create_index("ix_master_data_record_match", "master_data_record_references",
                    ["organization_id", "domain_id", "match_key_fingerprint", "status"])
    op.create_index("ix_master_data_record_domain_status", "master_data_record_references",
                    ["organization_id", "domain_id", "status"])


def downgrade():
    op.drop_index("ix_master_data_record_domain_status", table_name="master_data_record_references")
    op.drop_index("ix_master_data_record_match", table_name="master_data_record_references")
    op.drop_index("ix_master_data_record_references_organization_id", table_name="master_data_record_references")
    op.drop_table("master_data_record_references")
    op.drop_index("ix_master_data_domain_org_status", table_name="master_data_domains")
    op.drop_index("ix_master_data_domains_organization_id", table_name="master_data_domains")
    op.drop_table("master_data_domains")
