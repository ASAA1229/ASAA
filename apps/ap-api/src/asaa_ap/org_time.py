"""Company time zone (owner policy value, stored on the organization profile). There is no assumed default: when the time zone is not
set (or not a known IANA zone), business-date logic refuses with 409 policy_not_configured or, for read-only reports, reports the value
as not configured."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_governance.administration import OrganizationProfile


def org_zone(db: Session, org: str) -> ZoneInfo | None:
    name = db.scalar(select(OrganizationProfile.timezone).where(OrganizationProfile.organization_id == org))
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def org_today_or_none(db: Session, org: str, instant: datetime | None = None) -> date | None:
    zone = org_zone(db, org)
    return (instant or datetime.now(timezone.utc)).astimezone(zone).date() if zone else None


def org_today(db: Session, org: str, instant: datetime | None = None) -> date:
    value = org_today_or_none(db, org, instant)
    if value is None:
        raise HTTPException(status_code=409, detail={"code": "policy_not_configured", "policy": "organization_timezone",
                                                     "message": "The organization time zone is not set (or is not a valid IANA zone) on the organization profile."})
    return value
