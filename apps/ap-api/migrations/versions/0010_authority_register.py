"""Add governance decision and authority delegation registers."""

from alembic import op
import sqlalchemy as sa

revision = "0010_authority_register"
down_revision = "0009_master_data_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authority_delegations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("delegator_subject", sa.String(128), nullable=False),
        sa.Column("delegate_subject", sa.String(128), nullable=False),
        sa.Column("scope_code", sa.String(160), nullable=False),
        sa.Column("action_code", sa.String(160), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("evidence_reference", sa.String(500)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
    )
    op.create_index("ix_authority_delegations_organization_id", "authority_delegations", ["organization_id"])
    op.create_index("ix_authority_delegation_org_status", "authority_delegations", ["organization_id", "status"])
    op.create_index("ix_authority_delegation_org_subjects", "authority_delegations",
                    ["organization_id", "delegator_subject", "delegate_subject"])

    op.create_table(
        "governance_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("scope_reference", sa.String(500), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decision_maker_subject", sa.String(128), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_reference", sa.String(500)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
    )
    op.create_index("ix_governance_decisions_organization_id", "governance_decisions", ["organization_id"])
    op.create_index("ix_governance_decision_org_status", "governance_decisions", ["organization_id", "status"])
    op.create_index("ix_governance_decision_org_maker", "governance_decisions",
                    ["organization_id", "decision_maker_subject"])


def downgrade():
    op.drop_index("ix_governance_decision_org_maker", table_name="governance_decisions")
    op.drop_index("ix_governance_decision_org_status", table_name="governance_decisions")
    op.drop_index("ix_governance_decisions_organization_id", table_name="governance_decisions")
    op.drop_table("governance_decisions")
    op.drop_index("ix_authority_delegation_org_subjects", table_name="authority_delegations")
    op.drop_index("ix_authority_delegation_org_status", table_name="authority_delegations")
    op.drop_index("ix_authority_delegations_organization_id", table_name="authority_delegations")
    op.drop_table("authority_delegations")
