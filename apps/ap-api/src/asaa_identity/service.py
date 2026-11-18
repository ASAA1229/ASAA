"""Joiner / mover / leaver synchronisation, retry, revocation and reconciliation.

Design
  * Desired state is derived from authoritative ASAA records: the employee status and the
    approved, in-window role assignments (permissions of Active role templates).
  * Changes are queued in a transactional outbox (identity_sync_jobs) in the same transaction
    as the triggering change, then applied by process_due() through an IdentityProvider.
  * Jobs are level-triggered (desired state is recomputed at execution), so retries and
    duplicates converge on the correct state and are idempotent.
  * Transient provider failures back off exponentially; permanent failures or exhausted
    retries go to DeadLetter, are audited and logged at ERROR for alerting.
  * reconcile() compares desired state with the provider and optionally queues repairs.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asaa_ap.models import AuditEvent
from asaa_governance.authorization import AuthorizationAssignment, AuthorizationRoleTemplate
from asaa_identity.models import IdentitySubjectLink, IdentitySyncJob
from asaa_identity.provider import (AuthenticationProviderError, IdentityProvider, PermanentProviderError, ProviderError,
                                    ProviderUserNotFound, TransientProviderError, UserAttributes)
from asaa_ap.observability import redact
from asaa_people.models import Employee

log = logging.getLogger("asaa.identity_sync")
SYSTEM_ACTOR = "system:identity-sync"
ACTIVE_EMPLOYEE_STATUSES = {"Preboarding", "Active", "On Leave"}
OPERATIONS = {"joiner", "mover", "leaver"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _looks_like_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass(frozen=True)
class Desired:
    subject: str
    employee_id: str
    active: bool
    entitlements: frozenset[str]


def desired_states(db: Session, organization_id: str, now: datetime | None = None) -> tuple[dict[str, Desired], set[str]]:
    """Return (desired state per linked subject, subjects that hold grants but have no employee link)."""
    now = now or utcnow()
    links = db.execute(select(IdentitySubjectLink, Employee).join(Employee, Employee.id == IdentitySubjectLink.employee_id).where(
        IdentitySubjectLink.organization_id == organization_id, Employee.organization_id == organization_id)).all()
    grants: dict[str, set[str]] = {}
    rows = db.execute(select(AuthorizationAssignment, AuthorizationRoleTemplate).join(
        AuthorizationRoleTemplate, AuthorizationRoleTemplate.id == AuthorizationAssignment.role_template_id).where(
        AuthorizationAssignment.organization_id == organization_id, AuthorizationAssignment.status == "Approved",
        AuthorizationRoleTemplate.status == "Active")).all()
    for assignment, role in rows:
        start, end = aware(assignment.effective_from), aware(assignment.effective_to)
        if start <= now and (end is None or end > now):
            grants.setdefault(assignment.subject, set()).update(role.permissions)
    desired = {}
    for link, employee in links:
        active = employee.status in ACTIVE_EMPLOYEE_STATUSES
        desired[link.subject] = Desired(link.subject, employee.id, active, frozenset(grants.get(link.subject, set()) if active else set()))
    return desired, set(grants) - set(desired)


# ---------------------------------------------------------------- outbox

def enqueue(db: Session, organization_id: str, subject: str, operation: str, reason: str,
            requested_by: str, now: datetime | None = None, max_attempts: int = 5) -> IdentitySyncJob:
    """Queue a sync job in the caller's transaction (caller commits). De-duplicates pending work."""
    if operation not in OPERATIONS:
        raise ValueError("unknown operation")
    now = now or utcnow()
    existing = db.scalar(select(IdentitySyncJob).where(
        IdentitySyncJob.organization_id == organization_id, IdentitySyncJob.subject == subject,
        IdentitySyncJob.status == "Pending", IdentitySyncJob.operation == operation))
    if existing:
        return existing
    job = IdentitySyncJob(organization_id=organization_id, subject=subject, operation=operation, reason=reason,
                          requested_by=requested_by, requested_at=now, next_attempt_at=now, max_attempts=max_attempts,
                          idempotency_key=f"{operation}:{subject}:{now.isoformat()}:{reason}")
    db.add(job)
    db.flush()
    return job


def enqueue_for_employee(db: Session, organization_id: str, employee_id: str, operation: str, reason: str,
                         requested_by: str) -> IdentitySyncJob | None:
    link = db.scalar(select(IdentitySubjectLink).where(
        IdentitySubjectLink.organization_id == organization_id, IdentitySubjectLink.employee_id == employee_id))
    return enqueue(db, organization_id, link.subject, operation, reason, requested_by) if link else None


def enqueue_for_subject_if_linked(db: Session, organization_id: str, subject: str, operation: str, reason: str,
                                  requested_by: str) -> IdentitySyncJob | None:
    link = db.scalar(select(IdentitySubjectLink).where(
        IdentitySubjectLink.organization_id == organization_id, IdentitySubjectLink.subject == subject))
    return enqueue(db, organization_id, subject, operation, reason, requested_by) if link else None


# ---------------------------------------------------------------- execution

AUTH_FAILURE_BACKOFF_SECONDS = 900  # a refused credential is retried slowly: hammering a locked-out service account helps nobody


def _attributes(db: Session, organization_id: str, employee_id: str, allow_reenable: bool = False) -> UserAttributes:
    employee = db.scalar(select(Employee).where(Employee.id == employee_id, Employee.organization_id == organization_id))
    if not employee:
        return UserAttributes(allow_reenable=allow_reenable)
    return UserAttributes(display_name=f"{employee.first_name} {employee.last_name}", email=employee.work_email,
                          employee_reference=employee.employee_code, first_name=employee.first_name, last_name=employee.last_name,
                          allow_reenable=allow_reenable)


def apply_state(db: Session, provider: IdentityProvider, organization_id: str, subject: str, desired: Desired | None,
                operation: str | None = None) -> None:
    if desired is None or not desired.active:
        provider.disable_user(subject)
        provider.revoke_sessions(subject)
        if provider.get_user(subject) is not None:
            provider.set_entitlements(subject, frozenset())
        return
    # Only an explicit joiner job may re-enable an account that someone disabled outside ASAA; movers and reconciliation never do.
    provider.upsert_user(subject, _attributes(db, organization_id, desired.employee_id, allow_reenable=operation == "joiner"), True)
    provider.set_entitlements(subject, desired.entitlements)


def _record_steps(db: Session, job: IdentitySyncJob, provider: IdentityProvider) -> None:
    """One audit row per provisioning step the adapter reports (subject, provider id, action, group diff; no personal data)."""
    try:
        steps = provider.drain_audit()
    except Exception:  # noqa: BLE001 - auditing must not break the job loop
        return
    for step in steps:
        db.add(AuditEvent(organization_id=job.organization_id, actor_id=SYSTEM_ACTOR, action="identity_sync.provisioning_step",
                          entity_type="identity_sync_job", entity_id=job.id,
                          outcome="failure" if step.get("action") == "not_found" else "success",
                          details={"operation": job.operation, **{k: v for k, v in step.items() if k in {
                              "subject", "provider_id", "action", "groups_added", "groups_removed", "reason"}}}))


def _audit(db: Session, job: IdentitySyncJob, action: str, outcome: str, details: dict):
    db.add(AuditEvent(organization_id=job.organization_id, actor_id=SYSTEM_ACTOR, action=action,
                      entity_type="identity_sync_job", entity_id=job.id, outcome=outcome, details=details))


def backoff_seconds(attempts: int, base: int = 30, cap: int = 3600) -> int:
    return min(cap, base * (2 ** max(0, attempts - 1)))


def process_due(db: Session, provider: IdentityProvider, organization_id: str | None = None, now: datetime | None = None,
                limit: int = 50, backoff_base: int = 30, backoff_cap: int = 3600) -> dict:
    now = now or utcnow()
    stmt = select(IdentitySyncJob).where(IdentitySyncJob.status == "Pending", IdentitySyncJob.next_attempt_at <= now)
    if organization_id:
        stmt = stmt.where(IdentitySyncJob.organization_id == organization_id)
    jobs = db.scalars(stmt.order_by(IdentitySyncJob.next_attempt_at).limit(limit)).all()
    summary = {"processed": 0, "succeeded": 0, "retry_scheduled": 0, "dead_lettered": 0, "not_found": 0}
    desired_cache: dict[str, dict[str, Desired]] = {}
    for job in jobs:
        summary["processed"] += 1
        job.attempts += 1
        desired_map = desired_cache.get(job.organization_id)
        if desired_map is None:
            desired_map = desired_cache[job.organization_id] = desired_states(db, job.organization_id, now)[0]
        desired = desired_map.get(job.subject)
        if job.operation == "leaver":
            desired = None  # a leaver job always revokes, regardless of later re-hire
            current = desired_map.get(job.subject)
            if current is not None and current.active:
                desired = current  # re-hired before the job ran: converge on current truth
        try:
            try:
                apply_state(db, provider, job.organization_id, job.subject, desired, job.operation)
            finally:
                _record_steps(db, job, provider)
        except AuthenticationProviderError as exc:
            # The adapter's credentials were refused: alert an operator and retry slowly. A leaver is never dead-lettered for
            # this (the account must still be disabled once the credential is fixed); other jobs follow the normal retry budget.
            job.last_error = f"provider authentication: {redact(str(exc))}"[:300]
            _audit(db, job, "identity_sync.provider_auth_failed", "failure", {"operation": job.operation, "attempts": job.attempts})
            log.error("identity_provider_auth_failure", extra={"job_id": job.id, "operation": job.operation, "attempts": job.attempts})
            if job.operation != "leaver" and job.attempts >= job.max_attempts:
                _dead_letter(db, job, now, "retries_exhausted")
                summary["dead_lettered"] += 1
            else:
                job.next_attempt_at = now + timedelta(seconds=max(AUTH_FAILURE_BACKOFF_SECONDS, backoff_seconds(job.attempts, backoff_base, backoff_cap)))
                summary["retry_scheduled"] += 1
        except ProviderUserNotFound:
            job.status, job.completed_at, job.last_error = "NotFound", now, "provider has no account for this leaver"
            _audit(db, job, "identity_sync.not_found", "failure", {"operation": job.operation, "attempts": job.attempts})
            log.error("identity_sync_leaver_account_not_found", extra={"job_id": job.id, "operation": job.operation})
            summary["not_found"] += 1
        except TransientProviderError as exc:
            job.last_error = f"transient: {redact(str(exc))}"[:300]
            if job.attempts >= job.max_attempts:
                _dead_letter(db, job, now, "retries_exhausted")
                summary["dead_lettered"] += 1
            else:
                job.next_attempt_at = now + timedelta(seconds=backoff_seconds(job.attempts, backoff_base, backoff_cap))
                summary["retry_scheduled"] += 1
        except (PermanentProviderError, ProviderError) as exc:
            job.last_error = f"permanent: {redact(str(exc))}"[:300]
            _dead_letter(db, job, now, "permanent_error")
            summary["dead_lettered"] += 1
        except Exception as exc:  # noqa: BLE001 - one unexpected failure must not stop the remaining jobs
            db.rollback()
            job = db.get(IdentitySyncJob, job.id)
            job.attempts = max(job.attempts, 1)
            job.last_error = f"unexpected: {type(exc).__name__}"
            job.next_attempt_at = now + timedelta(seconds=backoff_seconds(job.attempts, backoff_base, backoff_cap))
            log.error("identity_sync_unexpected_error", extra={"job_id": job.id, "error_type": type(exc).__name__})
            summary["retry_scheduled"] += 1
        else:
            job.status, job.completed_at, job.last_error = "Succeeded", now, None
            _audit(db, job, "identity_sync.completed", "success", {
                "operation": job.operation, "attempts": job.attempts,
                "latency_seconds": round((now - aware(job.requested_at)).total_seconds(), 3)})
            summary["succeeded"] += 1
        db.commit()
    return summary


def _dead_letter(db: Session, job: IdentitySyncJob, now: datetime, cause: str):
    job.status, job.completed_at = "DeadLetter", now
    _audit(db, job, "identity_sync.dead_letter", "failure", {"operation": job.operation, "attempts": job.attempts, "cause": cause})
    log.error("identity_sync_dead_letter", extra={"job_id": job.id, "operation": job.operation, "attempts": job.attempts, "cause": cause})


def retry_dead_letter(db: Session, organization_id: str, job_id: str, now: datetime | None = None) -> IdentitySyncJob | None:
    job = db.scalar(select(IdentitySyncJob).where(IdentitySyncJob.id == job_id, IdentitySyncJob.organization_id == organization_id))
    if job is None or job.status != "DeadLetter":
        return None
    job.status, job.attempts, job.completed_at, job.next_attempt_at = "Pending", 0, None, now or utcnow()
    db.commit()
    return job


def status_summary(db: Session, organization_id: str, now: datetime | None = None, stale_after_seconds: int = 900) -> dict:
    now = now or utcnow()
    counts = dict(db.execute(select(IdentitySyncJob.status, func.count()).where(
        IdentitySyncJob.organization_id == organization_id).group_by(IdentitySyncJob.status)).all())
    pending = db.scalars(select(IdentitySyncJob).where(
        IdentitySyncJob.organization_id == organization_id, IdentitySyncJob.status == "Pending")).all()
    stale = [j for j in pending if (now - aware(j.requested_at)).total_seconds() > stale_after_seconds]
    oldest = max(((now - aware(j.requested_at)).total_seconds() for j in pending), default=0)
    return {"pending": counts.get("Pending", 0), "succeeded": counts.get("Succeeded", 0), "dead_letter": counts.get("DeadLetter", 0),
            "stale_pending": len(stale), "oldest_pending_seconds": round(oldest),
            "not_found": counts.get("NotFound", 0),
            "alert": bool(counts.get("DeadLetter", 0) or counts.get("NotFound", 0) or stale)}


# ---------------------------------------------------------------- reconciliation

def reconcile(db: Session, provider: IdentityProvider, organization_id: str, now: datetime | None = None,
              repair: bool = False, actor: str = SYSTEM_ACTOR) -> dict:
    now = now or utcnow()
    desired, unlinked = desired_states(db, organization_id, now)
    actual = {u.subject: u for u in provider.list_users()}
    drifts: list[dict] = []
    repairs: dict[str, str] = {}
    for subject, want in sorted(desired.items()):
        have = actual.get(subject)
        if want.active:
            if have is None:
                drifts.append({"subject": subject, "kind": "missing_in_provider"}); repairs[subject] = "joiner"; continue
            if not have.active:
                drifts.append({"subject": subject, "kind": "disabled_in_provider_but_should_be_active"}); repairs[subject] = "mover"
            if have.provider_id and _looks_like_uuid(subject) and have.provider_id.lower() != subject.lower():
                drifts.append({"subject": subject, "kind": "provider_id_differs_from_subject"})
            missing, extra = sorted(want.entitlements - have.entitlements), sorted(have.entitlements - want.entitlements)
            if missing:
                drifts.append({"subject": subject, "kind": "entitlement_missing", "entitlements": missing}); repairs[subject] = "mover"
            if extra:
                drifts.append({"subject": subject, "kind": "entitlement_extra", "entitlements": extra}); repairs[subject] = "mover"
        elif have is not None and (have.active or have.entitlements):
            drifts.append({"subject": subject, "kind": "should_be_disabled", "entitlements": sorted(have.entitlements)})
            repairs[subject] = "leaver"
    unmanaged = sorted(s for s, u in actual.items() if s not in desired and u.active)
    repaired = 0
    if repair:
        for subject, operation in repairs.items():
            enqueue(db, organization_id, subject, operation, "reconciliation", actor, now)
            repaired += 1
        if repaired:
            db.add(AuditEvent(organization_id=organization_id, actor_id=actor, action="identity_sync.reconciliation_repair",
                              entity_type="identity_reconciliation", entity_id=now.isoformat(), details={"jobs_queued": repaired}))
        db.commit()
    by_kind: dict[str, int] = {}
    for item in drifts:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    return {"generated_at": now.isoformat(), "managed_subjects": len(desired), "provider_users": len(actual),
            "in_sync": not drifts, "drift_count": len(drifts), "drift_by_kind": by_kind, "drifts": drifts,
            "unmanaged_active_users": unmanaged, "unlinked_subjects_with_grants": sorted(unlinked),
            "repair_jobs_queued": repaired, "jobs": status_summary(db, organization_id, now)}
