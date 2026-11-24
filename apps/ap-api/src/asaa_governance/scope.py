"""Data-scope resolution and enforcement (epic E02 / D3.14).

Rules (monotonic narrowing, never widening):
1. The token must still carry the permission (require_permission is always evaluated first).
2. Approved, effective-dated, unrevoked assignments of an Active role template that grant the permission can only NARROW it:
   the permission is limited to the union of those assignments' scopes; an Organization-scope assignment means the whole organization.
3. With no such assignment the token grant stays organization-wide ("narrow"/"token" modes). Mode "strict" refuses it with 403
   authorization_not_assigned. Mode "token" ignores assignments entirely (the pre-D3.14 behaviour).

Scope references look like "<type>:<id>". Unit scope includes descendant units (organization_units hierarchy); Department scope is
exactly that department unit (departments are organization units, employment records point at them with department_id).
Project scope matches an engagement id or its project_reference. Record scope is the id of the record itself.
Detail lookups outside scope must answer 404 (never 403), lists are filtered in SQL, writes and approvals check scope too.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import FunctionType
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.security import Principal, require_permission
from asaa_governance.administration import OrganizationUnit
from asaa_governance.authorization import (
    DEFAULT_SCOPE_MODE, SCOPE_MODES, AuthorizationAssignment, AuthorizationRoleTemplate, AuthorizationScopeSetting,
)


def _aware(value: datetime | None):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def scope_id(reference: str) -> str:
    """The identifier part of a scope reference ("unit:<id>" -> "<id>"; "record:hr_employee:<id>" -> "<id>")."""
    return reference.split(":")[-1].strip()


def get_scope_mode(db: Session, org_id: str) -> str:
    mode = db.scalar(select(AuthorizationScopeSetting.mode).where(AuthorizationScopeSetting.organization_id == org_id))
    return mode if mode in SCOPE_MODES else DEFAULT_SCOPE_MODE


def descendant_unit_ids(db: Session, org_id: str, roots) -> set[str]:
    rows = db.execute(select(OrganizationUnit.id, OrganizationUnit.parent_id).where(OrganizationUnit.organization_id == org_id)).all()
    children: dict[str, list[str]] = {}
    for unit_id, parent_id in rows:
        if parent_id:
            children.setdefault(parent_id, []).append(unit_id)
    known = {unit_id for unit_id, _ in rows}
    found, stack = set(), [r for r in roots if r in known]
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(children.get(current, []))
    return found


@dataclass(frozen=True)
class AccessScope:
    permission: str
    mode: str = DEFAULT_SCOPE_MODE
    unrestricted: bool = True
    units: frozenset = frozenset()  # already expanded with descendant units
    departments: frozenset = frozenset()
    projects: frozenset = frozenset()
    customers: frozenset = frozenset()
    records: frozenset = frozenset()
    assignment_ids: tuple = field(default_factory=tuple)

    @property
    def org_units(self) -> frozenset:
        return self.units | self.departments

    def summary(self) -> dict:
        return {"permission": self.permission, "mode": self.mode, "unrestricted": self.unrestricted,
                "units": sorted(self.units), "departments": sorted(self.departments), "projects": sorted(self.projects),
                "customers": sorted(self.customers), "records": sorted(self.records), "assignment_ids": list(self.assignment_ids)}

    def clause(self, *, unit=None, customer=None, project=None, record=None):
        """SQL predicate selecting rows inside this scope. Each argument is a column (matched with IN) or a function taking the id
        list and returning a predicate; pass only the dimensions the entity has. A dimension the entity lacks matches nothing."""
        if self.unrestricted:
            return true()
        parts = []
        for spec, ids in ((unit, self.org_units), (customer, self.customers), (project, self.projects), (record, self.records)):
            if spec is None or not ids:
                continue
            parts.append(spec(sorted(ids)) if isinstance(spec, FunctionType) else spec.in_(sorted(ids)))
        return or_(*parts) if parts else false()

    # Single-value checks for writes that reference another record (for example moving someone into a department).
    def allows_unit(self, unit_id) -> bool:
        return self.unrestricted or (unit_id is not None and unit_id in self.org_units)

    def allows_customer(self, customer_id) -> bool:
        return self.unrestricted or (customer_id is not None and customer_id in self.customers)

    def allows_record(self, record_id) -> bool:
        return self.unrestricted or (record_id is not None and record_id in self.records)

    def require_unrestricted(self):
        """For writes that create a record which cannot be placed inside a restricted scope."""
        if not self.unrestricted:
            raise HTTPException(status_code=403, detail={"code": "authorization_out_of_scope"})


def not_found(label: str):
    return HTTPException(status_code=404, detail=f"{label} not found")


def active_assignments(db: Session, org_id: str, subject: str, now: datetime | None = None, permission: str | None = None):
    """(assignment, role) pairs that are Approved, effective now, of an Active role template, optionally granting `permission`."""
    now = now or datetime.now(timezone.utc)
    rows = db.execute(select(AuthorizationAssignment, AuthorizationRoleTemplate).join(
        AuthorizationRoleTemplate, AuthorizationRoleTemplate.id == AuthorizationAssignment.role_template_id).where(
        AuthorizationAssignment.organization_id == org_id, AuthorizationAssignment.subject == subject,
        AuthorizationAssignment.status == "Approved", AuthorizationRoleTemplate.status == "Active",
        AuthorizationRoleTemplate.organization_id == org_id)).all()
    out = []
    for assignment, role in rows:
        if _aware(assignment.effective_from) > now or (assignment.effective_to and _aware(assignment.effective_to) <= now):
            continue
        if permission is not None and permission not in (role.permissions or []):
            continue
        out.append((assignment, role))
    return out


def build_scope(db: Session, org_id: str, subject: str, permission: str, mode: str | None = None, now: datetime | None = None) -> AccessScope:
    """Resolve the scope of one permission for a principal whose token already carries it. Raises 403 in strict mode when unassigned."""
    mode = mode or get_scope_mode(db, org_id)
    if mode == "token":
        return AccessScope(permission, mode)
    matched = active_assignments(db, org_id, subject, now, permission)
    if not matched:
        if mode == "strict":
            raise HTTPException(status_code=403, detail={"code": "authorization_not_assigned"})
        return AccessScope(permission, mode)
    if any(role.scope_type == "Organization" for _, role in matched):
        return AccessScope(permission, mode, True, assignment_ids=tuple(a.id for a, _ in matched))
    buckets = {"Unit": set(), "Department": set(), "Project": set(), "Customer": set(), "Record": set()}
    for assignment, role in matched:
        if role.scope_type in buckets:
            buckets[role.scope_type].add(scope_id(assignment.scope_reference))
    return AccessScope(permission, mode, False, units=frozenset(descendant_unit_ids(db, org_id, buckets["Unit"])),
                       departments=frozenset(buckets["Department"]), projects=frozenset(buckets["Project"]),
                       customers=frozenset(buckets["Customer"]), records=frozenset(buckets["Record"]),
                       assignment_ids=tuple(a.id for a, _ in matched))


def require_scoped_permission(permission: str):
    """Dependency: the token must carry `permission` (server-side), then the resolved AccessScope is returned (cached per request).
    Use the scope in list queries (scope.clause(...)), detail lookups (404 when outside) and writes."""
    def dependency(request: Request, db: Annotated[Session, Depends(get_db)],
                   principal: Annotated[Principal, Depends(require_permission(permission))]) -> AccessScope:
        cache = request.scope.setdefault("asaa_access_scopes", {})
        key = (principal.organization_id, principal.subject, permission)
        if key not in cache:
            cache[key] = build_scope(db, principal.organization_id, principal.subject, permission)
        return cache[key]
    return dependency


def check_scope_reference_exists(db: Session, org_id: str, scope_type: str, reference: str):
    """An assignment scope must point at something that exists in this organization (Record scopes are opaque record ids)."""
    target = scope_id(reference)
    ok = True
    if scope_type in ("Unit", "Department"):
        ok = db.scalar(select(OrganizationUnit.id).where(OrganizationUnit.id == target, OrganizationUnit.organization_id == org_id)) is not None
    elif scope_type == "Customer":
        from asaa_ap.models import ARCustomer
        ok = db.scalar(select(ARCustomer.id).where(ARCustomer.id == target, ARCustomer.organization_id == org_id)) is not None
    elif scope_type == "Project":
        from asaa_delivery.models import Engagement
        ok = db.scalar(select(Engagement.id).where(Engagement.organization_id == org_id,
                                                   or_(Engagement.id == target, Engagement.project_reference == target)).limit(1)) is not None
    if not ok:
        raise HTTPException(status_code=422, detail={"code": "authorization_scope_reference_not_found"})


# ---- administration routes: scope mode and effective access ------------------------------------------------------------------

from fastapi import APIRouter, Header, Query  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

from asaa_governance.authorization import audit as _audit, is_sensitive_permission, utcnow  # noqa: E402

router = APIRouter(prefix="/api/v1/authorization", tags=["Authorization Governance"])


class ScopeModeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = Field(pattern="^(token|narrow|strict)$")
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/scope-mode")
def read_scope_mode(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("authorization:role:read"))):
    row = db.get(AuthorizationScopeSetting, principal.organization_id)
    return {"mode": get_scope_mode(db, principal.organization_id), "default": DEFAULT_SCOPE_MODE, "modes": list(SCOPE_MODES),
            "updated_by": row.updated_by if row else None, "updated_at": row.updated_at if row else None, "reason": row.reason if row else None}


@router.put("/scope-mode")
def write_scope_mode(payload: ScopeModeUpdate, db: Session = Depends(get_db),
                     principal: Principal = Depends(require_permission("authorization:scope-mode:write")),
                     x_correlation_id: str | None = Header(default=None)):
    """Privileged and audited. strict refuses a token permission that has no approved assignment; token ignores assignments."""
    row = db.get(AuthorizationScopeSetting, principal.organization_id)
    previous = row.mode if row else DEFAULT_SCOPE_MODE
    if row is None:
        row = AuthorizationScopeSetting(organization_id=principal.organization_id, mode=payload.mode, updated_by=principal.subject, reason=payload.reason)
        db.add(row)
    else:
        row.mode, row.updated_by, row.updated_at, row.reason = payload.mode, principal.subject, utcnow(), payload.reason
    _audit(db, principal, "authorization_scope_mode.changed", "authorization_scope_setting", principal.organization_id,
           {"from": previous, "to": payload.mode, "reason": payload.reason}, x_correlation_id)
    db.commit()
    return {"mode": payload.mode, "previous": previous}


@router.get("/effective-access")
def effective_access(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("authorization:assignment:read")),
                     subject: str | None = Query(default=None, min_length=1, max_length=128)):
    """What a principal can reach: approved effective assignments and the resolved scope per permission. Without `subject` the caller's own
    token permissions are resolved too; for someone else only assignment-granted permissions are known server-side."""
    org = principal.organization_id
    target = subject or principal.subject
    mode = get_scope_mode(db, org)
    pairs = active_assignments(db, org, target)
    permissions = {p for _, role in pairs for p in (role.permissions or [])}
    own = target == principal.subject
    if own:
        permissions |= set(principal.permissions)
    resolved = {}
    for permission in sorted(permissions):
        try:
            scope = build_scope(db, org, target, permission, mode)
            resolved[permission] = {**scope.summary(), "in_token": own and permission in principal.permissions if own else None,
                                    "sensitive": is_sensitive_permission(permission), "refused": False}
        except HTTPException:
            resolved[permission] = {"permission": permission, "mode": mode, "unrestricted": False, "refused": True, "refusal": "authorization_not_assigned",
                                    "in_token": permission in principal.permissions, "sensitive": is_sensitive_permission(permission)}
    return {"subject": target, "mode": mode, "token_permissions_known": own,
            "assignments": [{"id": a.id, "role_code": r.role_code, "role_name": r.name, "scope_type": r.scope_type, "scope_reference": a.scope_reference,
                             "effective_from": a.effective_from, "effective_to": a.effective_to, "permissions": r.permissions,
                             "sensitive_permissions": sorted(p for p in r.permissions if is_sensitive_permission(p))} for a, r in pairs],
            "permissions": resolved,
            "note": "Access is never wider than the token permission. Assignments narrow it; with no assignment for a permission the mode decides (narrow: organization-wide via the token; strict: refused)."}
