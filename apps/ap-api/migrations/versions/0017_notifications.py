"""Notification outbox: templates, preferences and messages."""
from alembic import op
import sqlalchemy as sa

revision = "0017_notifications"
down_revision = "0016_identity_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("subject_template", sa.String(300), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("allowed_variables", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("organization_id", "code", "channel", name="uq_notification_template"),
    )
    op.create_index("ix_notification_templates_organization_id", "notification_templates", ["organization_id"])
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "subject", "channel", name="uq_notification_preference"),
    )
    op.create_index("ix_notification_preferences_organization_id", "notification_preferences", ["organization_id"])
    op.create_table(
        "notification_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("recipient_subject", sa.String(128), nullable=False),
        sa.Column("template_code", sa.String(80), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("subject_text", sa.String(300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(300)),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("correlation_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_notification_idempotency"),
    )
    op.create_index("ix_notification_messages_organization_id", "notification_messages", ["organization_id"])
    op.create_index("ix_notification_due", "notification_messages", ["organization_id", "status", "next_attempt_at"])


def downgrade():
    op.drop_table("notification_messages")
    op.drop_table("notification_preferences")
    op.drop_table("notification_templates")
