"""GET /api/v1/reports/summary: counts and totals by status over existing records.

Each section is returned only when the caller holds the read permission of its source records, so a report never reveals more than
the record APIs would. Money is aggregated per currency (never summed across currencies). Payroll amounts and salaries are NEVER
included. Every section carries lineage (source tables) and the generation time so freshness is visible.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import ARCustomer, ARInvoice, ARReceipt, ARReceiptAllocation, Supplier
from asaa_ap.procurement_models import PurchaseRequest
from asaa_ap.security import Principal, get_principal
from asaa_governance.authority import AuthorityDelegation, GovernanceDecision
from asaa_identity.models import IdentitySyncJob
from asaa_notifications.models import NotificationMessage
from asaa_people.models import Employee, LeaveRequest
from asaa_registers.catalog import TYPES
from asaa_registers.models import GovernedRecord
from asaa_workforce_finance.models import ExpenseClaim, Timesheet

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def by_status(db: Session, model, org: str, column=None) -> dict:
    column = column or model.status
    return {status: count for status, count in db.execute(select(column, func.count()).where(model.organization_id == org).group_by(column)).all()}


def money_by_currency(rows) -> dict:
    return {currency: str(Decimal(total or 0).quantize(Decimal("0.01"))) for currency, total in rows}


@router.get("/summary")
def summary(db: Annotated[Session, Depends(get_db)], principal: Annotated[Principal, Depends(get_principal)]):
    org, perms = principal.organization_id, principal.permissions
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "currency_note": "Amounts are per currency and are never converted or summed across currencies.",
                 "sections": {}}

    def section(key, label, sources, data):
        out["sections"][key] = {"label": label, "sources": sources, "data": data}

    if "ar:invoice:read" in perms:
        issued = ARInvoice.status.in_(["Issued", "Partially Paid"])
        billed = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARInvoice.total)).where(ARInvoice.organization_id == org, issued).group_by(ARInvoice.currency)).all())
        paid = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARReceiptAllocation.amount)).join(ARInvoice, ARInvoice.id == ARReceiptAllocation.invoice_id)
                                            .where(ARInvoice.organization_id == org, issued).group_by(ARInvoice.currency)).all())
        outstanding = {c: str(Decimal(billed[c]) - Decimal(paid.get(c, "0"))) for c in billed}
        overdue = db.scalar(select(func.count()).where(ARInvoice.organization_id == org, issued, ARInvoice.due_date < datetime.now(timezone.utc).date())) or 0
        section("receivables", "Receivables", ["ar_invoices", "ar_receipt_allocations"],
                {"invoices_by_status": by_status(db, ARInvoice, org), "outstanding_by_currency": outstanding, "overdue_invoices": overdue})
    if "ar:customer:read" in perms:
        section("customers", "Customers", ["ar_customers"], {"customers_by_status": by_status(db, ARCustomer, org)})
    if "ar:receipt:read" in perms:
        section("receipts", "Receipts", ["ar_receipts"], {"receipts_by_status": by_status(db, ARReceipt, org),
                "recorded_by_currency": money_by_currency(db.execute(select(ARReceipt.currency, func.sum(ARReceipt.amount)).where(ARReceipt.organization_id == org).group_by(ARReceipt.currency)).all()),
                "note": "Recording a receipt is not bank settlement."})
    if "supplier:read" in perms:
        section("suppliers", "Suppliers", ["ap_suppliers"], {"suppliers_by_status": by_status(db, Supplier, org)})
    if "procurement:request:read:all" in perms:
        section("procurement", "Purchase requests", ["ap_purchase_requests"], {"requests_by_status": by_status(db, PurchaseRequest, org)})
    if "expense:claim:read:all" in perms:
        section("expenses", "Expense claims", ["expense_claims"], {"claims_by_status": by_status(db, ExpenseClaim, org),
                "claimed_by_currency": money_by_currency(db.execute(select(ExpenseClaim.currency, func.sum(ExpenseClaim.amount)).where(ExpenseClaim.organization_id == org).group_by(ExpenseClaim.currency)).all())})
    if "tms:timesheet:read:all" in perms:
        section("timesheets", "Timesheets", ["work_timesheets"], {"timesheets_by_status": by_status(db, Timesheet, org)})
    if "hr:employee:read" in perms:
        section("workforce", "Workforce", ["hr_employees"], {"employees_by_status": by_status(db, Employee, org), "employees_by_type": by_status(db, Employee, org, Employee.employment_type),
                "note": "Headcount only. Compensation and payroll are intentionally excluded."})
    if "hr:leave:read" in perms:
        section("leave", "Leave requests", ["hr_leave_requests"], {"requests_by_status": by_status(db, LeaveRequest, org)})
    if "governance:delegation:read" in perms:
        section("delegations", "Authority delegations", ["authority_delegations"], {"delegations_by_status": by_status(db, AuthorityDelegation, org)})
    if "governance:decision:read" in perms:
        section("decisions", "Decision register", ["governance_decisions"], {"decisions_by_status": by_status(db, GovernanceDecision, org)})
    readable = [t for t in TYPES if f"register:{t}:read" in perms]
    if readable:
        rows = db.execute(select(GovernedRecord.register_type, GovernedRecord.status, func.count()).where(
            GovernedRecord.organization_id == org, GovernedRecord.register_type.in_(readable)).group_by(GovernedRecord.register_type, GovernedRecord.status)).all()
        data: dict = {t: {} for t in readable}
        for rtype, status, count in rows:
            data[rtype][status] = count
        section("registers", "Governed registers", ["governed_records"], {"by_register": data})
    if "notification:outbox:read" in perms:
        section("notifications", "Notification delivery", ["notification_messages"], {"messages_by_status": by_status(db, NotificationMessage, org)})
    if "identity:sync:read" in perms:
        section("identity_sync", "Identity synchronisation", ["identity_sync_jobs"], {"jobs_by_status": by_status(db, IdentitySyncJob, org)})
    return out
