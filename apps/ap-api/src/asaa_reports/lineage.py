"""Reporting data freshness and lineage, kept separate from report presentation.

SOURCES is the single declaration of every dataset a report may read: the owning module, the permission needed to see its freshness, and
the timestamp column that shows when its newest record arrived. Freshness is observed from the data itself (newest record time and row
count per organization), never assumed. A source is stale only when the caller supplies a maximum age; the owner has not set one.
Payroll and compensation datasets are deliberately not listed.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_attendance.models import AttendanceRecord
from asaa_ap.database import get_db
from asaa_ap.models import ARCreditNote, ARInvoice, ARReceipt, Supplier
from asaa_ap.procurement_models import PurchaseRequest
from asaa_ap.security import Principal, require_permission
from asaa_delivery.models import Engagement
from asaa_payables.models import PaymentBatch, PurchaseOrder, SupplierInvoice
from asaa_people.models import Employee, LeaveRequest
from asaa_workforce_finance.models import ExpenseClaim, Timesheet

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

# name -> (model, timestamp column, owning module, permission required to see its freshness)
SOURCES: dict = {
    "ar_invoices": (ARInvoice, ARInvoice.created_at, "asaa_ap.ar_service", "ar:invoice:read"),
    "ar_receipts": (ARReceipt, ARReceipt.created_at, "asaa_ap.ar_service", "ar:receipt:read"),
    "ar_credit_notes": (ARCreditNote, ARCreditNote.created_at, "asaa_ap.ar_credit", "ar:credit:read"),
    "ap_suppliers": (Supplier, Supplier.updated_at, "asaa_ap.service", "supplier:read"),
    "ap_purchase_requests": (PurchaseRequest, PurchaseRequest.created_at, "asaa_ap.purchase_requests", "procurement:request:read:all"),
    "ap_purchase_orders": (PurchaseOrder, PurchaseOrder.created_at, "asaa_payables.api", "ap:po:read"),
    "ap_supplier_invoices": (SupplierInvoice, SupplierInvoice.created_at, "asaa_payables.api", "ap:invoice:read"),
    "ap_payment_batches": (PaymentBatch, PaymentBatch.created_at, "asaa_payables.api", "ap:payment:read"),
    "hr_employees": (Employee, Employee.updated_at, "asaa_people.api", "hr:employee:read"),
    "hr_leave_requests": (LeaveRequest, LeaveRequest.created_at, "asaa_people.workflows", "hr:leave:read"),
    "att_records": (AttendanceRecord, AttendanceRecord.created_at, "asaa_attendance.api", "attendance:record:read:all"),
    "expense_claims": (ExpenseClaim, ExpenseClaim.created_at, "asaa_workforce_finance.api", "expense:claim:read:all"),
    "work_timesheets": (Timesheet, Timesheet.created_at, "asaa_workforce_finance.api", "tms:timesheet:read:all"),
    "dlv_engagements": (Engagement, Engagement.created_at, "asaa_delivery.api", "delivery:engagement:read"),
}

# report -> datasets it reads. Presentation code references these names; it never embeds its own lineage claims.
REPORT_LINEAGE: dict[str, list[str]] = {
    "receivables_aging": ["ar_invoices", "ar_receipts", "ar_credit_notes"],
    "payables_aging": ["ap_supplier_invoices"],
    "customer_statement": ["ar_invoices", "ar_receipts", "ar_credit_notes"],
    "attendance_summary": ["att_records", "hr_leave_requests"],
    "reports_summary": ["ar_invoices", "ar_receipts", "ar_credit_notes", "ap_suppliers", "ap_purchase_requests", "expense_claims", "work_timesheets", "hr_employees", "hr_leave_requests"],
}


def aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


@router.get("/lineage")
def lineage(principal: Annotated[Principal, Depends(require_permission("report:lineage:read"))]):
    """Declared dataset registry and which reports read which datasets, limited to datasets the caller may read. Requires report:lineage:read."""
    visible = {name for name, (_, _, _, perm) in SOURCES.items() if perm in principal.permissions}
    return {"datasets": [{"name": n, "owner_module": SOURCES[n][2], "required_permission": SOURCES[n][3]} for n in sorted(visible)],
            "reports": {r: {"datasets": [d for d in ds if d in visible], "hidden_dataset_count": len([d for d in ds if d not in visible])} for r, ds in REPORT_LINEAGE.items()}}


@router.get("/freshness")
def freshness(db: Annotated[Session, Depends(get_db)], principal: Annotated[Principal, Depends(require_permission("report:lineage:read"))], max_age_hours: float | None = Query(default=None, gt=0, le=87600)):
    """Newest record time, row count and age per dataset for this organization. `stale` is reported only when max_age_hours is supplied."""
    now = datetime.now(timezone.utc)
    out = []
    for name, (model, column, owner, perm) in sorted(SOURCES.items()):
        if perm not in principal.permissions:
            continue
        count, newest = db.execute(select(func.count(), func.max(column)).where(model.organization_id == principal.organization_id)).one()
        newest = aware(newest)
        age = round((now - newest).total_seconds() / 3600, 2) if newest else None
        entry = {"dataset": name, "owner_module": owner, "record_count": count, "newest_record_at": newest.isoformat() if newest else None, "age_hours": age}
        if max_age_hours is not None:
            entry["stale"] = newest is None or age > max_age_hours
        out.append(entry)
    return {"generated_at": now.isoformat(), "max_age_hours": max_age_hours, "datasets": out,
            "note": "Freshness reflects the newest record created in each dataset, not an external feed or batch schedule. No threshold is applied unless max_age_hours is supplied."}
