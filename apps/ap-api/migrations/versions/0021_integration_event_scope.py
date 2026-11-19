"""Scope ecosystem event ids per organization (composite primary key) and store the producer-declared severity."""
from alembic import op
import sqlalchemy as sa

revision = "0021_integration_event_scope"
down_revision = "0020_integration_events"
branch_labels = None
depends_on = None

INDEXES = [("ix_integration_events_organization_id", ["organization_id"]), ("ix_integration_events_source", ["source"]),
           ("ix_integration_events_type", ["type"]), ("ix_integration_events_project", ["project"]),
           ("ix_integration_events_org_occurred", ["organization_id", "occurred_at"])]
COLUMNS = ["id", "organization_id", "source", "type", "project", "subject", "correlation_id", "severity", "occurred_at", "received_at",
           "data", "received_by"]


def _table(name, composite: bool, with_declared: bool):
    columns = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False, primary_key=composite),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("type", sa.String(120), nullable=False),
        sa.Column("project", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(200)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("severity", sa.String(16), nullable=False),
    ]
    if with_declared:
        columns.append(sa.Column("declared_severity", sa.String(16), nullable=False, server_default="info"))
    columns += [
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("received_by", sa.String(128), nullable=False),
    ]
    op.create_table(name, *columns)


def upgrade():
    _table("integration_events_new", True, True)
    names = ", ".join(COLUMNS[:8] + ["declared_severity"] + COLUMNS[8:])
    values = ", ".join(COLUMNS[:8] + ["severity"] + COLUMNS[8:])  # existing rows: declared severity = the stored severity
    op.execute(f"INSERT INTO integration_events_new ({names}) SELECT {values} FROM integration_events")
    for name, _cols in INDEXES:
        op.drop_index(name, table_name="integration_events")
    op.drop_table("integration_events")
    op.rename_table("integration_events_new", "integration_events")
    for name, cols in INDEXES:
        op.create_index(name, "integration_events", cols)


def downgrade():
    # Fails (unique violation) if two organizations hold the same event id; resolve that before downgrading.
    _table("integration_events_old", False, False)
    names = ", ".join(COLUMNS)
    op.execute(f"INSERT INTO integration_events_old ({names}) SELECT {names} FROM integration_events")
    for name, _cols in INDEXES:
        op.drop_index(name, table_name="integration_events")
    op.drop_table("integration_events")
    op.rename_table("integration_events_old", "integration_events")
    for name, cols in INDEXES:
        op.create_index(name, "integration_events", cols)
