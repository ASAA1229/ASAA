"""Identity lifecycle synchronisation: subject links and transactional outbox jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0016_identity_sync"
down_revision = "0015_authorization_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_subject_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id"), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "employee_id", name="uq_identity_link_org_employee"),
        sa.UniqueConstraint("organization_id", "subject", name="uq_identity_link_org_subject"),
    )
    op.create_index("ix_identity_subject_links_organization_id", "identity_subject_links", ["organization_id"])
    op.create_table(
        "identity_sync_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("operation", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(300)),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_identity_job_idempotency"),
    )
    op.create_index("ix_identity_sync_jobs_organization_id", "identity_sync_jobs", ["organization_id"])
    op.create_index("ix_identity_job_due", "identity_sync_jobs", ["organization_id", "status", "next_attempt_at"])


def downgrade():
    op.drop_table("identity_sync_jobs")
    op.drop_table("identity_subject_links")
