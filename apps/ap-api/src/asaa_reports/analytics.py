"""Dashboard analytics computed from the datasets declared in the lineage registry (asaa_reports.lineage).

Every response names the datasets it read (with their owning module and observed freshness) so presentation never invents lineage.
A dataset is used only if the caller holds its read permission; metrics that need an unreadable dataset are omitted and reported in
`withheld`. Money is per currency, never converted. Nothing here is a forecast, a bank balance or a statutory figure.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from statistics import median
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_ap.ar_service import amount_credited, amount_paid
from asaa_ap.database import get_db
from asaa_ap.models import ARInvoice
from asaa_ap.security import Principal, require_permission
from asaa_payables.models import PurchaseOrder, SupplierInvoice
from asaa_reports.lineage import REPORT_LINEAGE, SOURCES, aware
from asaa_workforce_finance.models import ExpenseClaim

router = APIRouter(prefix="/api/v1/reports/analytics", tags=["Reports"])
Db = Annotated[Session, Depends(get_db)]
ANALYTICS = Depends(require_permission("report:analytics:read"))

REPORT_LINEAGE.update({
    "trends": sorted(SOURCES),
    "review_cycle_times": ["ap_purchase_orders", "ap_supplier_invoices", "expense_claims"],
    "working_capital_position": ["ar_invoices", "ar_receipts", "ar_credit_notes", "ap_supplier_invoices"],
})

# dataset -> (model, created column, reviewed-at column) for datasets that go through an independent review
REVIEWED = {
    "ap_purchase_orders": (PurchaseOrder, PurchaseOrder.created_at, PurchaseOrder.reviewed_at),
    "ap_supplier_invoices": (SupplierInvoice, SupplierInvoice.created_at, SupplierInvoice.reviewed_at),
    "expense_claims": (ExpenseClaim, ExpenseClaim.created_at, ExpenseClaim.reviewed_at),
}


def provenance(db: Session, org: str, names: list[str]) -> list[dict]:
    out = []
    for name in names:
        model, column, owner, _ = SOURCES[name]
        count, newest = db.execute(select(func.count(), func.max(column)).where(model.organization_id == org)).one()
        newest = aware(newest)
        out.append({"dataset": name, "owner_module": owner, "record_count": count, "newest_record_at": newest.isoformat() if newest else None})
    return out


def readable(principal: Principal, names: list[str]) -> tuple[list[str], list[str]]:
    ok = [n for n in names if SOURCES[n][3] in principal.permissions]
    return ok, [n for n in names if n not in ok]


def period_key(value: datetime | date, grain: str) -> str:
    if grain == "month":
        return f"{value.year:04d}-{value.month:02d}"
    iso = value.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"


@router.get("/trends")
def trends(db: Db, principal: Annotated[Principal, ANALYTICS], dataset: str = Query(pattern=r"^[a-z_]{3,40}$"), grain: str = Query(default="month", pattern="^(month|week)$"),
           periods: int = Query(default=12, ge=1, le=60)):
    """Records created per period for one declared dataset (zero-filled gaps are not invented: only periods with records appear)."""
    if dataset not in SOURCES:
        raise HTTPException(status_code=404, detail={"code": "unknown_dataset"})
    if SOURCES[dataset][3] not in principal.permissions:
        raise HTTPException(status_code=403, detail="Permission denied")
    model, column, _, _ = SOURCES[dataset]
    counts: dict[str, int] = defaultdict(int)
    for (stamp,) in db.execute(select(column).where(model.organization_id == principal.organization_id)).all():
        if stamp is not None:
            counts[period_key(stamp, grain)] += 1
    keys = sorted(counts)[-periods:]
    return {"dataset": dataset, "grain": grain, "series": [{"period": k, "records": counts[k]} for k in keys], "lineage": provenance(db, principal.organization_id, [dataset]),
            "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/review-cycle-times")
def review_cycle_times(db: Db, principal: Annotated[Principal, ANALYTICS]):
    """Hours from creation to independent review, for reviewed records, per dataset (count, mean, median, longest)."""
    names, withheld = readable(principal, list(REVIEWED))
    out = {}
    for name in names:
        model, created, reviewed = REVIEWED[name]
        hours = [(aware(r) - aware(c)).total_seconds() / 3600 for c, r in db.execute(select(created, reviewed).where(model.organization_id == principal.organization_id, reviewed.is_not(None))).all()]
        out[name] = {"reviewed_records": len(hours), "mean_hours": round(sum(hours) / len(hours), 2) if hours else None, "median_hours": round(median(hours), 2) if hours else None,
                     "longest_hours": round(max(hours), 2) if hours else None}
    return {"cycle_times": out, "withheld": withheld, "lineage": provenance(db, principal.organization_id, names), "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/working-capital-position")
def working_capital_position(db: Db, principal: Annotated[Principal, ANALYTICS]):
    """Receivables outstanding versus approved-but-unpaid payables per currency. A derived position, NOT a cash balance."""
    names = REPORT_LINEAGE["working_capital_position"]
    ok, withheld = readable(principal, names)
    org = principal.organization_id
    ar: dict[str, Decimal] = defaultdict(Decimal)
    ap: dict[str, Decimal] = defaultdict(Decimal)
    if "ar_invoices" in ok:
        for inv in db.scalars(select(ARInvoice).where(ARInvoice.organization_id == org, ARInvoice.status.in_(["Issued", "Partially Paid"]))).all():
            ar[inv.currency] += inv.total - amount_paid(db, inv.id) - amount_credited(db, inv.id)
    if "ap_supplier_invoices" in ok:
        for inv in db.scalars(select(SupplierInvoice).where(SupplierInvoice.organization_id == org, SupplierInvoice.status.in_(["Approved", "In Payment Batch"]))).all():
            ap[inv.currency] += inv.total
    currencies = sorted(set(ar) | set(ap))
    return {"by_currency": {c: {"receivables_outstanding": str(ar.get(c, Decimal("0")).quantize(Decimal("0.01"))), "payables_approved_unpaid": str(ap.get(c, Decimal("0")).quantize(Decimal("0.01"))),
                               "net": str((ar.get(c, Decimal("0")) - ap.get(c, Decimal("0"))).quantize(Decimal("0.01")))} for c in currencies},
            "withheld": withheld, "lineage": provenance(db, org, ok), "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Derived from invoices only. Excludes payroll, expenses awaiting reimbursement, bank balances and unapproved supplier invoices."}
