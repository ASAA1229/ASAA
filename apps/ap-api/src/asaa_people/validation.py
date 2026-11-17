"""Cross-domain reference validation for people records (service layer)."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_governance.administration import OrganizationUnit


def require_department(db: Session, organization_id: str, department_id: str | None) -> None:
    """New employment records must reference an organization unit of the same organization that has not been rejected.
    Legacy free-text values already stored on older records are never rewritten and stay readable; only new writes are checked."""
    if department_id is None:
        return
    unit_status = db.scalar(select(OrganizationUnit.status).where(
        OrganizationUnit.id == department_id, OrganizationUnit.organization_id == organization_id))
    if unit_status is None or unit_status == "Rejected":
        raise HTTPException(status_code=422, detail={"code": "employment_department_not_found"})
