"""GET /api/v1/reports/summary: counts and totals by status over existing records.

Each section is returned only when the caller holds the read permission of its source records, so a report never reveals more than
the record APIs would. Sections are also narrowed to the caller's data scope for that permission (customer, unit/department or record, the
same mechanism as the record APIs); a dataset that cannot be scoped is withheld from a caller whose scope for it is restricted. Money is aggregated per currency (never summed across currencies). Payroll amounts and salaries are NEVER
included. Every section carries lineage (source tables) and the generation time so freshness is visible.
"""
import calendar
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.ar_service import customer_clause, invoice_clause, receipt_clause
from asaa_ap.org_time import org_today_or_none
from asaa_ap.models import ARCreditNote, ARCustomer, ARDebitNote, ARInvoice, ARReceipt, ARReceiptAllocation, Supplier
from asaa_ap.procurement_models import PurchaseRequest
from asaa_ap.security import Principal, get_principal
from asaa_governance.scope import build_scope
from asaa_people.scoping import employee_clause, payroll_entry_clause
from asaa_governance.authority import AuthorityDelegation, GovernanceDecision
from asaa_identity.models import IdentitySyncJob
from asaa_notifications.models import NotificationMessage
from asaa_people.models import Employee, LeaveRequest, PayrollEntry, PayrollRun
from asaa_registers.catalog import TYPES
from asaa_registers.models import GovernedRecord
from asaa_workforce_finance.models import ExpenseClaim, Timesheet

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

PERIOD = re.compile(r"^([0-9]{4})(?:-(?:Q([1-4])|(0[1-9]|1[0-2])))?$")


def period_bounds(label: str):
    """Fiscal period label (YYYY, YYYY-Qn or YYYY-MM, calendar-aligned until the owner sets a fiscal calendar) to (first, last) dates."""
    m = PERIOD.match(label or "")
    if not m:
        return None
    year, quarter, month = int(m.group(1)), m.group(2), m.group(3)
    if quarter:
        first_month, last_month = (int(quarter) - 1) * 3 + 1, int(quarter) * 3
    elif month:
        first_month = last_month = int(month)
    else:
        first_month, last_month = 1, 12
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, first_month, 1), date(year, last_month, last_day)


def by_status(db: Session, model, org: str, column=None, scoped=None) -> dict:
    column = column or model.status
    return {status: count for status, count in db.execute(select(column, func.count()).where(model.organization_id == org, scoped if scoped is not None else true()).group_by(column)).all()}


def money_by_currency(rows) -> dict:
    return {currency: str(Decimal(total or 0).quantize(Decimal("0.01"))) for currency, total in rows}


@router.get("/summary")
def summary(db: Annotated[Session, Depends(get_db)], principal: Annotated[Principal, Depends(get_principal)]):
    org, perms = principal.organization_id, principal.permissions
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "currency_note": "Amounts are per currency and are never converted or summed across currencies.",
                 "sections": {}}

    def section(key, label, sources, data):
        out["sections"][key] = {"label": label, "sources": sources, "data": data}

    memo: dict = {}

    def scope_of(permission):
        """The caller's data scope for one permission, or None when the token lacks it (or strict mode has no assignment): the section is then withheld."""
        if permission not in perms:
            return None
        if permission not in memo:
            try:
                memo[permission] = build_scope(db, org, principal.subject, permission)
            except HTTPException:
                memo[permission] = None
        return memo[permission]

    def whole(permission):
        """True only for an organization-wide grant. Datasets without a customer or unit dimension are reported only on this condition."""
        scope = scope_of(permission)
        return scope is not None and scope.unrestricted

    inv, rcpt, cust = scope_of("ar:invoice:read"), scope_of("ar:receipt:read"), scope_of("ar:customer:read")
    if inv is not None:
        inv_where = invoice_clause(inv)
        issued = ARInvoice.status.in_(["Issued", "Partially Paid"])
        billed = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARInvoice.total)).where(ARInvoice.organization_id == org, issued, inv_where).group_by(ARInvoice.currency)).all())
        paid = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARReceiptAllocation.amount)).join(ARInvoice, ARInvoice.id == ARReceiptAllocation.invoice_id)
                                            .where(ARInvoice.organization_id == org, issued, inv_where).group_by(ARInvoice.currency)).all())
        credited = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARCreditNote.amount)).join(ARInvoice, ARInvoice.id == ARCreditNote.invoice_id)
                                                .where(ARInvoice.organization_id == org, issued, inv_where, ARCreditNote.status == "Approved").group_by(ARInvoice.currency)).all())
        debited = money_by_currency(db.execute(select(ARInvoice.currency, func.sum(ARDebitNote.amount)).join(ARInvoice, ARInvoice.id == ARDebitNote.invoice_id)
                                               .where(ARInvoice.organization_id == org, issued, inv_where, ARDebitNote.status == "Approved").group_by(ARInvoice.currency)).all())
        outstanding = {c: str(Decimal(billed[c]) - Decimal(paid.get(c, "0")) - Decimal(credited.get(c, "0")) + Decimal(debited.get(c, "0"))) for c in billed}
        today = org_today_or_none(db, org)  # None = organization time zone not configured: overdue is not judged
        overdue = (db.scalar(select(func.count()).where(ARInvoice.organization_id == org, issued, inv_where, ARInvoice.due_date < today)) or 0) if today is not None else None
        section("receivables", "Receivables", ["ar_invoices", "ar_receipt_allocations"],
                {"invoices_by_status": by_status(db, ARInvoice, org, scoped=inv_where), "outstanding_by_currency": outstanding, "overdue_invoices": overdue})
    if inv is not None and whole("expense:claim:read:all"):
        issued = ARInvoice.status.in_(["Issued", "Partially Paid"])
        paid_by_invoice = select(ARReceiptAllocation.invoice_id, func.sum(ARReceiptAllocation.amount).label("paid")).group_by(ARReceiptAllocation.invoice_id).subquery()
        credit_by_invoice = select(ARCreditNote.invoice_id, func.sum(ARCreditNote.amount).label("credited")).where(ARCreditNote.status == "Approved").group_by(ARCreditNote.invoice_id).subquery()
        open_rows = db.execute(select(ARInvoice.currency, ARInvoice.due_date, ARInvoice.total - func.coalesce(paid_by_invoice.c.paid, 0) - func.coalesce(credit_by_invoice.c.credited, 0))
                               .outerjoin(paid_by_invoice, paid_by_invoice.c.invoice_id == ARInvoice.id).outerjoin(credit_by_invoice, credit_by_invoice.c.invoice_id == ARInvoice.id)
                               .where(ARInvoice.organization_id == org, issued, invoice_clause(inv))).all()
        inflow: dict = {}
        for currency, due_date, amount in open_rows:  # grouped in Python so the report is identical on SQLite and PostgreSQL
            month = due_date.strftime("%Y-%m")
            bucket = inflow.setdefault(currency, {})
            bucket[month] = str((Decimal(bucket.get(month, "0")) + Decimal(amount or 0)).quantize(Decimal("0.01")))
        owed = money_by_currency(db.execute(select(ExpenseClaim.currency, func.sum(ExpenseClaim.amount)).where(ExpenseClaim.organization_id == org, ExpenseClaim.status == "Approved")
                                            .group_by(ExpenseClaim.currency)).all())
        section("cash_outlook", "Cash outlook (derived)", ["ar_invoices", "ar_receipt_allocations", "expense_claims"],
                {"expected_receipts_by_currency_and_due_month": inflow, "approved_expenses_awaiting_reimbursement_by_currency": owed,
                 "note": "Derived from receivable due dates and approved expense claims. This is NOT a bank balance and includes no supplier payments or payroll."})
    if rcpt is not None and inv is not None:
        allocated_by_receipt = select(ARReceiptAllocation.receipt_id, func.sum(ARReceiptAllocation.amount).label("allocated")).group_by(ARReceiptAllocation.receipt_id).subquery()
        receipt_rows = db.execute(select(ARReceipt.id, ARReceipt.currency, ARReceipt.amount, func.coalesce(allocated_by_receipt.c.allocated, 0))
                                  .outerjoin(allocated_by_receipt, allocated_by_receipt.c.receipt_id == ARReceipt.id).where(ARReceipt.organization_id == org, receipt_clause(rcpt))).all()
        unallocated: dict = {}
        exceptions = []
        for rid, currency, amount, allocated in receipt_rows:
            gap = Decimal(amount) - Decimal(allocated)
            if gap != 0:
                unallocated[currency] = unallocated.get(currency, Decimal(0)) + gap
                exceptions.append({"type": "receipt_not_fully_allocated" if gap > 0 else "receipt_over_allocated", "reference": rid, "currency": currency, "difference": str(gap)})
        paid_per_invoice = dict(db.execute(select(ARReceiptAllocation.invoice_id, func.sum(ARReceiptAllocation.amount)).join(ARInvoice, ARInvoice.id == ARReceiptAllocation.invoice_id)
                                           .where(ARInvoice.organization_id == org, invoice_clause(inv)).group_by(ARReceiptAllocation.invoice_id)).all())
        credit_per_invoice = dict(db.execute(select(ARCreditNote.invoice_id, func.sum(ARCreditNote.amount)).where(ARCreditNote.organization_id == org, ARCreditNote.status == "Approved",
                                                    ARCreditNote.invoice_id.in_(select(ARInvoice.id).where(ARInvoice.organization_id == org, invoice_clause(inv))))
                                             .group_by(ARCreditNote.invoice_id)).all())
        for inv in db.scalars(select(ARInvoice).where(ARInvoice.organization_id == org, invoice_clause(inv), ARInvoice.status.in_(["Issued", "Partially Paid", "Paid"]))).all():
            paid = Decimal(paid_per_invoice.get(inv.id, 0))
            credit = Decimal(credit_per_invoice.get(inv.id, 0))
            if inv.status == "Paid" and paid + credit != Decimal(inv.total):
                exceptions.append({"type": "paid_invoice_allocation_mismatch", "reference": inv.id, "currency": inv.currency, "difference": str(Decimal(inv.total) - paid - credit)})
            if inv.status == "Issued" and paid != 0:
                exceptions.append({"type": "issued_invoice_has_allocations", "reference": inv.id, "currency": inv.currency, "difference": str(paid)})
            if paid + credit > Decimal(inv.total):
                exceptions.append({"type": "invoice_over_allocated", "reference": inv.id, "currency": inv.currency, "difference": str(paid - Decimal(inv.total))})
        section("reconciliation", "Receivables reconciliation", ["ar_receipts", "ar_receipt_allocations", "ar_invoices"],
                {"unallocated_receipts_by_currency": {c: str(v.quantize(Decimal("0.01"))) for c, v in unallocated.items()}, "exception_count": len(exceptions), "exceptions": exceptions[:100],
                 "note": "Internal consistency checks between receipts, allocations and invoices. Not a bank reconciliation: no bank statement is compared."})
    pay = scope_of("payroll:accounting:read")
    if pay is not None:
        closed = db.execute(select(PayrollRun.currency, func.count(func.distinct(PayrollRun.id)), func.sum(PayrollEntry.gross_amount), func.sum(PayrollEntry.deduction_total), func.sum(PayrollEntry.net_amount))
                            .join(PayrollEntry, PayrollEntry.run_id == PayrollRun.id).where(PayrollRun.organization_id == org, PayrollRun.status == "Closed",
                                                                                   payroll_entry_clause(pay, org)).group_by(PayrollRun.currency)).all()
        section("payroll_accounting", "Payroll accounting totals (closed runs)", ["payroll_runs", "payroll_entries"],
                {"closed_run_totals_by_currency": {c: {"runs": n, "gross": str(Decimal(g or 0)), "deductions": str(Decimal(d or 0)), "net": str(Decimal(nt or 0))} for c, n, g, d, nt in closed},
                 "note": "Totals only, for approved finance exports. No journal posting, tax or statutory calculation is performed (pending owner accounting policy)."})
    if whole("register:budget:read") and whole("expense:claim:read:all"):
        budgets = db.scalars(select(GovernedRecord).where(GovernedRecord.organization_id == org, GovernedRecord.register_type == "budget", GovernedRecord.status == "Approved")).all()
        planned: dict = {}
        not_comparable = []
        for b in budgets:
            data = b.data or {}
            key = (data.get("currency"), data.get("fiscal_period"))
            if period_bounds(key[1]) is None:
                not_comparable.append({"code": b.code, "fiscal_period": key[1], "reason": "fiscal period is not YYYY, YYYY-Qn or YYYY-MM"})
                continue
            planned[key] = planned.get(key, Decimal(0)) + Decimal(str(data.get("planned_amount", "0")))
        lines = []
        for (currency, label), amount in sorted(planned.items()):
            first, last = period_bounds(label)
            actual = db.scalar(select(func.sum(ExpenseClaim.amount)).where(ExpenseClaim.organization_id == org, ExpenseClaim.currency == currency, ExpenseClaim.status.in_(["Approved", "Reimbursement Recorded"]),
                                                                           ExpenseClaim.expense_date >= first, ExpenseClaim.expense_date <= last)) or 0
            actual = Decimal(actual)
            lines.append({"currency": currency, "fiscal_period": label, "planned": str(amount.quantize(Decimal("0.01"))), "actual_expenses": str(actual.quantize(Decimal("0.01"))),
                          "variance": str((amount - actual).quantize(Decimal("0.01"))), "over_budget": actual > amount})
        section("budget_variance", "Budget versus expense actuals (derived)", ["governed_records", "expense_claims"],
                {"lines": lines, "not_comparable": not_comparable,
                 "note": "Approved budget lines per currency and calendar-aligned period against approved or reimbursed expense claims only. Supplier invoices, payroll and cost-centre mapping are not included and approval thresholds are pending owner policy. Not a forecast."})
    if cust is not None:
        section("customers", "Customers", ["ar_customers"], {"customers_by_status": by_status(db, ARCustomer, org, scoped=customer_clause(cust))})
    if rcpt is not None:
        section("receipts", "Receipts", ["ar_receipts"], {"receipts_by_status": by_status(db, ARReceipt, org, scoped=receipt_clause(rcpt)),
                "recorded_by_currency": money_by_currency(db.execute(select(ARReceipt.currency, func.sum(ARReceipt.amount)).where(ARReceipt.organization_id == org, receipt_clause(rcpt)).group_by(ARReceipt.currency)).all()),
                "note": "Recording a receipt is not bank settlement."})
    if whole("supplier:read"):
        section("suppliers", "Suppliers", ["ap_suppliers"], {"suppliers_by_status": by_status(db, Supplier, org)})
    if whole("procurement:request:read:all"):
        section("procurement", "Purchase requests", ["ap_purchase_requests"], {"requests_by_status": by_status(db, PurchaseRequest, org)})
    if whole("expense:claim:read:all"):
        section("expenses", "Expense claims", ["expense_claims"], {"claims_by_status": by_status(db, ExpenseClaim, org),
                "claimed_by_currency": money_by_currency(db.execute(select(ExpenseClaim.currency, func.sum(ExpenseClaim.amount)).where(ExpenseClaim.organization_id == org).group_by(ExpenseClaim.currency)).all())})
    if whole("tms:timesheet:read:all"):
        section("timesheets", "Timesheets", ["work_timesheets"], {"timesheets_by_status": by_status(db, Timesheet, org)})
    emp = scope_of("hr:employee:read")
    if emp is not None:
        emp_where = employee_clause(emp, org)
        section("workforce", "Workforce", ["hr_employees"], {"employees_by_status": by_status(db, Employee, org, scoped=emp_where), "employees_by_type": by_status(db, Employee, org, Employee.employment_type, scoped=emp_where),
                "note": "Headcount only. Compensation and payroll are intentionally excluded."})
    leave = scope_of("hr:leave:read")
    if leave is not None:  # leave follows the employee's unit/department
        section("leave", "Leave requests", ["hr_leave_requests"], {"requests_by_status": by_status(
            db, LeaveRequest, org, scoped=LeaveRequest.employee_id.in_(select(Employee.id).where(Employee.organization_id == org, employee_clause(leave, org))))})
    if whole("governance:delegation:read"):
        section("delegations", "Authority delegations", ["authority_delegations"], {"delegations_by_status": by_status(db, AuthorityDelegation, org)})
    if whole("governance:decision:read"):
        section("decisions", "Decision register", ["governance_decisions"], {"decisions_by_status": by_status(db, GovernanceDecision, org)})
    readable = [t for t in TYPES if whole(f"register:{t}:read")]
    if readable:
        rows = db.execute(select(GovernedRecord.register_type, GovernedRecord.status, func.count()).where(
            GovernedRecord.organization_id == org, GovernedRecord.register_type.in_(readable)).group_by(GovernedRecord.register_type, GovernedRecord.status)).all()
        data: dict = {t: {} for t in readable}
        for rtype, status, count in rows:
            data[rtype][status] = count
        section("registers", "Governed registers", ["governed_records"], {"by_register": data})
    if whole("notification:outbox:read"):
        section("notifications", "Notification delivery", ["notification_messages"], {"messages_by_status": by_status(db, NotificationMessage, org)})
    if whole("identity:sync:read"):
        section("identity_sync", "Identity synchronisation", ["identity_sync_jobs"], {"jobs_by_status": by_status(db, IdentitySyncJob, org)})
    return out
