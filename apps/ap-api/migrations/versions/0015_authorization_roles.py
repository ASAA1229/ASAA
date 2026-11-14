"""Add governed role templates and scoped access assignment records."""
from alembic import op
import sqlalchemy as sa

revision = "0015_authorization_roles"
down_revision = "0014_org_unit_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authorization_role_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("role_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("scope_type", sa.String(24), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
        sa.UniqueConstraint("organization_id", "role_code", name="uq_auth_role_org_code"),
    )
    op.create_index("ix_authorization_role_templates_organization_id", "authorization_role_templates", ["organization_id"])
    op.create_index("ix_auth_role_org_status", "authorization_role_templates", ["organization_id", "status"])
    op.create_table(
        "authorization_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("role_template_id", sa.String(36), sa.ForeignKey("authorization_role_templates.id"), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("scope_reference", sa.String(300), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(1000)),
    )
    op.create_index("ix_authorization_assignments_organization_id", "authorization_assignments", ["organization_id"])
    op.create_index("ix_auth_assignment_org_status", "authorization_assignments", ["organization_id", "status"])
    op.create_index("ix_auth_assignment_org_subject", "authorization_assignments", ["organization_id", "subject"])


def downgrade():
    op.drop_index("ix_auth_assignment_org_subject", table_name="authorization_assignments")
    op.drop_index("ix_auth_assignment_org_status", table_name="authorization_assignments")
    op.drop_index("ix_authorization_assignments_organization_id", table_name="authorization_assignments")
    op.drop_table("authorization_assignments")
    op.drop_index("ix_auth_role_org_status", table_name="authorization_role_templates")
    op.drop_index("ix_authorization_role_templates_organization_id", table_name="authorization_role_templates")
    op.drop_table("authorization_role_templates")
