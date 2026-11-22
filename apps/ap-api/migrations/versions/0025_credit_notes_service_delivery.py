"""Receivables credit notes and the service-delivery module (services, engagements, milestones, work orders)."""
from alembic import op
import sqlalchemy as sa

revision = "0025_credit_notes_service_delivery"
down_revision = "0024_attendance_shifts"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "ar_credit_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("ar_customers.id"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", TS),
        sa.Column("review_reason", sa.String(500)),
    )
    op.create_index("ix_ar_credit_notes_organization_id", "ar_credit_notes", ["organization_id"])
    op.create_index("ix_ar_credit_note_org_invoice", "ar_credit_notes", ["organization_id", "invoice_id"])
    op.create_index("ix_ar_credit_note_org_status", "ar_credit_notes", ["organization_id", "status"])
    op.create_table(
        "dlv_services",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_subject", sa.String(128)),
        sa.Column("service_tier", sa.String(60)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("review_reason", sa.String(500)),
        sa.UniqueConstraint("organization_id", "code", name="uq_dlv_service_org_code"),
    )
    op.create_index("ix_dlv_services_organization_id", "dlv_services", ["organization_id"])
    op.create_table(
        "dlv_engagements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("ar_customers.id"), nullable=False),
        sa.Column("service_id", sa.String(36), sa.ForeignKey("dlv_services.id")),
        sa.Column("sow_reference", sa.String(160)),
        sa.Column("project_reference", sa.String(160)),
        sa.Column("owner_subject", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("currency", sa.String(3)),
        sa.Column("budget_amount", sa.Numeric(18, 2)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_dlv_engagement_org_code"),
    )
    op.create_index("ix_dlv_engagements_organization_id", "dlv_engagements", ["organization_id"])
    op.create_index("ix_dlv_engagement_org_status", "dlv_engagements", ["organization_id", "status"])
    op.create_table(
        "dlv_milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("engagement_id", sa.String(36), sa.ForeignKey("dlv_engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("deliverable", sa.String(1000)),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("billable_amount", sa.Numeric(18, 2)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("delivered_by", sa.String(128)),
        sa.Column("delivered_at", TS),
        sa.Column("delivery_evidence", sa.String(500)),
        sa.Column("accepted_by", sa.String(128)),
        sa.Column("accepted_at", TS),
        sa.Column("client_acceptance_reference", sa.String(300)),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("ar_invoices.id")),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_index("ix_dlv_milestones_organization_id", "dlv_milestones", ["organization_id"])
    op.create_index("ix_dlv_milestone_org_engagement", "dlv_milestones", ["organization_id", "engagement_id"])
    op.create_table(
        "dlv_work_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("engagement_id", sa.String(36), sa.ForeignKey("dlv_engagements.id")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String(12), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("assignee_employee_id", sa.String(36), sa.ForeignKey("hr_employees.id")),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("completion_evidence", sa.String(1000)),
        sa.Column("completed_by", sa.String(128)),
        sa.Column("completed_at", TS),
        sa.Column("verified_by", sa.String(128)),
        sa.Column("verified_at", TS),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_dlv_work_orders_organization_id", "dlv_work_orders", ["organization_id"])
    op.create_index("ix_dlv_work_order_org_status", "dlv_work_orders", ["organization_id", "status"])


def downgrade():
    for table in ("dlv_work_orders", "dlv_milestones", "dlv_engagements", "dlv_services", "ar_credit_notes"):
        op.drop_table(table)
