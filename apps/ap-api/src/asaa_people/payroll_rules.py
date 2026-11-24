"""Configurable payroll rules mechanism. Rule sets are entered by the owner and approved by a different person; calculation applies only an
APPROVED set that covers the run period. No rate or statutory rule is built in or seeded: with no approved set the calculation refuses."""
from datetime import date, datetime, timezone
from decimal import (Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP)
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_integration.emitter import emit_for_audit
from asaa_governance.scope import AccessScope, require_scoped_permission
from asaa_people.scoping import check_payroll_run_scope, payroll_entry_clause
from asaa_people.models import PayrollEntry, PayrollEntryLine, PayrollPeriod, PayrollRuleLine, PayrollRuleSet, PayrollRun
from asaa_people.schemas import CompensationDecision, StrictModel

router = APIRouter(prefix="/api/v1/payroll", tags=["Salaries and Payroll"])
Db = Annotated[Session, Depends(get_db)]
ROUNDING = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN, "down": ROUND_DOWN, "up": ROUND_UP, "ceiling": ROUND_CEILING, "floor": ROUND_FLOOR}
CENT = Decimal("0.01")


class RuleLineIn(StrictModel):
    line_type: str = Field(pattern="^(deduction|contribution|tax)$")
    code: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=300)
    basis: str = Field(pattern="^(gross|fixed)$")
    rate: Decimal | None = Field(default=None, ge=0, le=1, max_digits=9, decimal_places=6)
    fixed_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    cap_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    borne_by: str = Field(default="employee", pattern="^(employee|employer)$")

    @model_validator(mode="after")
    def basis_consistent(self):
        if self.basis == "gross" and (self.rate is None or self.fixed_amount is not None):
            raise ValueError("a gross-basis line needs a rate and no fixed_amount")
        if self.basis == "fixed" and (self.fixed_amount is None or self.rate is not None):
            raise ValueError("a fixed-basis line needs a fixed_amount and no rate")
        if self.line_type in {"deduction", "tax"} and self.borne_by != "employee":
            raise ValueError("deduction and tax lines are borne by the employee; use a contribution line for employer cost")
        return self


class RuleSetCreate(StrictModel):
    code: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    currency: str = Field(pattern="^[A-Z]{3}$")
    effective_from: date
    effective_to: date | None = None
    rounding_mode: str = Field(pattern="^(half_up|half_even|down|up|ceiling|floor)$")  # explicit: the owner must choose
    lines: list[RuleLineIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        if len({line.code for line in self.lines}) != len(self.lines):
            raise ValueError("line codes must be unique within a rule set")
        return self


def _audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, correlation_id=correlation_id))
    emit_for_audit(db, principal.organization_id, principal.subject, action, entity_id, details, correlation_id)


def _plain(row):
    return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}


def _view(db, row):
    lines = db.scalars(select(PayrollRuleLine).where(PayrollRuleLine.organization_id == row.organization_id, PayrollRuleLine.rule_set_id == row.id)
                       .order_by(PayrollRuleLine.sequence)).all()
    return {**_plain(row), "lines": [_plain(line) for line in lines]}


def _overlaps(a_from, a_to, b_from, b_to):
    return a_from <= (b_to or date.max) and b_from <= (a_to or date.max)


@router.post("/rule-sets", status_code=201)
def create_rule_set(payload: RuleSetCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:rules:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    if db.scalar(select(PayrollRuleSet.id).where(PayrollRuleSet.organization_id == principal.organization_id, PayrollRuleSet.code == payload.code)):
        raise HTTPException(status_code=409, detail={"code": "payroll_rule_set_code_exists"})
    for other in db.scalars(select(PayrollRuleSet).where(
            PayrollRuleSet.organization_id == principal.organization_id, PayrollRuleSet.currency == payload.currency,
            PayrollRuleSet.status.in_({"Pending Approval", "Approved"}))).all():
        if _overlaps(payload.effective_from, payload.effective_to, other.effective_from, other.effective_to):
            raise HTTPException(status_code=409, detail={"code": "payroll_rule_set_period_overlap", "conflicting_rule_set_id": other.id})
    row = PayrollRuleSet(organization_id=principal.organization_id, created_by=principal.subject,
                         **payload.model_dump(exclude={"lines"}))
    db.add(row)
    db.flush()
    for index, line in enumerate(payload.lines, start=1):
        db.add(PayrollRuleLine(organization_id=principal.organization_id, rule_set_id=row.id, sequence=index, **line.model_dump()))
    db.flush()
    _audit(db, principal, "payroll_rule_set.proposed", "payroll_rule_set", row.id,
           {"code": row.code, "currency": row.currency, "line_count": len(payload.lines), "rounding_mode": row.rounding_mode}, x_correlation_id)
    db.commit()
    return _view(db, row)


@router.get("/rule-sets")
def list_rule_sets(db: Db, principal: Annotated[Principal, Depends(require_permission("payroll:rules:read"))]):
    rows = db.scalars(select(PayrollRuleSet).where(PayrollRuleSet.organization_id == principal.organization_id)
                      .order_by(PayrollRuleSet.effective_from.desc())).all()
    return [_view(db, row) for row in rows]


@router.post("/rule-sets/{rule_set_id}/decision")
def decide_rule_set(rule_set_id: str, payload: CompensationDecision, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:rules:approve"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(PayrollRuleSet).where(PayrollRuleSet.id == rule_set_id, PayrollRuleSet.organization_id == principal.organization_id).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Payroll rule set not found")
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_rule_set"})
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "payroll_rule_set_not_pending", "current_status": row.status})
    if payload.decision == "Approved":
        for other in db.scalars(select(PayrollRuleSet).where(
                PayrollRuleSet.organization_id == principal.organization_id, PayrollRuleSet.currency == row.currency,
                PayrollRuleSet.status == "Approved", PayrollRuleSet.id != row.id)).all():
            if _overlaps(row.effective_from, row.effective_to, other.effective_from, other.effective_to):
                raise HTTPException(status_code=409, detail={"code": "payroll_rule_set_period_overlap", "conflicting_rule_set_id": other.id})
    row.status = payload.decision
    row.approved_by = principal.subject
    row.approved_at = datetime.now(timezone.utc)
    row.approval_note = payload.approval_note
    _audit(db, principal, "payroll_rule_set.decided", "payroll_rule_set", row.id, {"decision": payload.decision, "code": row.code}, x_correlation_id)
    db.commit()
    return _view(db, row)


def compute_line(line, gross: Decimal, mode: str):
    """Pure Decimal calculation of one line: gross x rate (or the fixed amount), capped, then rounded once with the rule set's mode."""
    if line.basis == "gross":
        basis_amount, raw = gross, gross * Decimal(line.rate)
    else:
        basis_amount = raw = Decimal(line.fixed_amount)
    if line.cap_amount is not None:
        raw = min(raw, Decimal(line.cap_amount))
    return basis_amount, raw.quantize(CENT, rounding=ROUNDING[mode])


@router.get("/runs/{run_id}/entries/{entry_id}/lines")
def list_entry_lines(run_id: str, entry_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("payroll:read"))],
                     scope: Annotated[AccessScope, Depends(require_scoped_permission("payroll:read"))]):
    if not scope.unrestricted and not db.scalar(select(PayrollEntry.id).where(
            PayrollEntry.id == entry_id, PayrollEntry.run_id == run_id, PayrollEntry.organization_id == principal.organization_id,
            payroll_entry_clause(scope, principal.organization_id))):
        raise HTTPException(status_code=404, detail="Payroll entry not found")  # an entry outside the data scope is not found
    rows = db.scalars(select(PayrollEntryLine).where(
        PayrollEntryLine.organization_id == principal.organization_id, PayrollEntryLine.run_id == run_id, PayrollEntryLine.entry_id == entry_id)
        .order_by(PayrollEntryLine.created_at, PayrollEntryLine.code)).all()
    return [_plain(row) for row in rows]


@router.post("/runs/{run_id}/calculate")
def calculate_payroll_run(run_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:entry:write"))],
    scope: Annotated[AccessScope, Depends(require_scoped_permission("payroll:entry:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    """Apply the single APPROVED rule set whose effective dates cover the run period to each entry's entered gross amount.
    With none, refuse (policy_not_configured). Recalculation replaces earlier calculated lines. Every outcome is audited."""
    run = db.scalar(select(PayrollRun).where(PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id).with_for_update())
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    check_payroll_run_scope(db, run, principal.organization_id, scope, whole=True)  # recalculation touches every entry of the run
    period = db.scalar(select(PayrollPeriod).where(PayrollPeriod.id == run.period_id, PayrollPeriod.organization_id == principal.organization_id))
    candidates = [r for r in db.scalars(select(PayrollRuleSet).where(
        PayrollRuleSet.organization_id == principal.organization_id, PayrollRuleSet.currency == run.currency, PayrollRuleSet.status == "Approved")).all()
        if period and r.effective_from <= period.start_date and (r.effective_to is None or r.effective_to >= period.end_date)]
    if not candidates:
        _audit(db, principal, "payroll_run.calculation_refused", "payroll_run", run.id, {"policy": "payroll_calculation_rules"}, x_correlation_id)
        db.commit()
        raise HTTPException(status_code=409, detail={
            "code": "policy_not_configured", "policy": "payroll_calculation_rules",
            "message": "No owner-approved payroll rule set covers this run period and currency; calculation is refused. Enter and reconcile amounts manually."})
    if run.status not in {"Draft", "Changes Requested"}:
        raise HTTPException(status_code=409, detail={"code": "payroll_run_not_editable"})
    if len(candidates) > 1:
        raise HTTPException(status_code=409, detail={"code": "payroll_rule_set_ambiguous", "rule_set_ids": [c.id for c in candidates]})
    rule_set = candidates[0]
    rule_lines = db.scalars(select(PayrollRuleLine).where(PayrollRuleLine.organization_id == principal.organization_id, PayrollRuleLine.rule_set_id == rule_set.id)
                            .order_by(PayrollRuleLine.sequence)).all()
    entries = db.scalars(select(PayrollEntry).where(PayrollEntry.organization_id == principal.organization_id, PayrollEntry.run_id == run.id)).all()
    if not entries:
        raise HTTPException(status_code=409, detail={"code": "payroll_run_empty"})
    employee_all = employer_all = Decimal("0.00")
    for entry in entries:
        db.execute(delete(PayrollEntryLine).where(PayrollEntryLine.organization_id == principal.organization_id, PayrollEntryLine.entry_id == entry.id))
        employee_total = employer_total = Decimal("0.00")
        for line in rule_lines:
            basis_amount, amount = compute_line(line, Decimal(entry.gross_amount), rule_set.rounding_mode)
            db.add(PayrollEntryLine(organization_id=principal.organization_id, entry_id=entry.id, run_id=run.id, rule_set_id=rule_set.id, rule_line_id=line.id,
                                    line_type=line.line_type, code=line.code, borne_by=line.borne_by, basis_amount=basis_amount, rate=line.rate, amount=amount,
                                    rounding_mode=rule_set.rounding_mode, source_references=entry.source_references, created_by=principal.subject))
            if line.borne_by == "employee":
                employee_total += amount
            else:
                employer_total += amount
        if employee_total > entry.gross_amount:
            db.rollback()
            raise HTTPException(status_code=409, detail={"code": "payroll_deductions_exceed_gross", "employee_id": entry.employee_id})
        entry.deduction_total = employee_total
        entry.net_amount = Decimal(entry.gross_amount) - employee_total
        entry.breakdown = {**(entry.breakdown or {}), "calculation": {"rule_set_id": rule_set.id, "rule_set_code": rule_set.code, "rounding_mode": rule_set.rounding_mode,
                                                                       "employer_contribution_total": str(employer_total)}}
        employee_all += employee_total
        employer_all += employer_total
    result = {"run_id": run.id, "rule_set_id": rule_set.id, "entry_count": len(entries), "rounding_mode": rule_set.rounding_mode,
              "employee_deduction_total": str(employee_all), "employer_contribution_total": str(employer_all)}
    _audit(db, principal, "payroll_run.calculated", "payroll_run", run.id, {**result, "rule_set_code": rule_set.code}, x_correlation_id)
    db.commit()
    return result
