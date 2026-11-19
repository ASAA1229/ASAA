#!/usr/bin/env python
"""Seed the four ecosystem projects (ASAA, JARVIS, TEMPLATES, PORTFOLIO) into the `project` register of one organization.

Idempotent: a project whose code already exists in that organization's project register (any revision) is left untouched.
Records are created as Draft (maker-checker: a seeded record must still be submitted and independently approved by people)
with classification and repository URL taken from contracts/ecosystem/v1/ecosystem-registry.json.

  python scripts/seed_ecosystem_projects.py --org-id asaa
  python scripts/seed_ecosystem_projects.py --org-id asaa --database-url postgresql+psycopg://migrator@host/asaa --dry-run

The database URL comes from --database-url or ASAA_AP_DATABASE_URL; passwords are never accepted on the command line (use the environment).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from urllib.parse import urlparse

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT.parents[1] / "contracts" / "ecosystem" / "v1" / "ecosystem-registry.json"
TITLES = {"ASAA": "ASAA Enterprise Operating Platform", "JARVIS": "JARVIS", "TEMPLATES": "Templates", "PORTFOLIO": "Portfolio"}
DEFAULT_OWNER = "system:ecosystem-seed"


def project_entries(registry: dict) -> list[dict]:
    entries = []
    for project in registry["projects"]:
        code = project["code"]
        entries.append({
            "code": code,
            "title": TITLES.get(code, code.title()),
            "summary": "Ecosystem project seeded from the ASAA ecosystem registry. Services: " + ", ".join(s["service"] for s in project.get("services", [])) + ".",
            "data": {"project_status": "Active", "classification": project["classification"], "repository_url": project["repository"]},
        })
    return entries


def seed(session, org_id: str, registry: dict, owner: str = DEFAULT_OWNER, dry_run: bool = False) -> dict:
    from asaa_ap.models import AuditEvent
    from asaa_registers.catalog import validate_data
    from asaa_registers.models import GovernedRecord

    result = {"created": [], "skipped": []}
    for entry in project_entries(registry):
        exists = session.scalar(select(GovernedRecord.id).where(
            GovernedRecord.organization_id == org_id, GovernedRecord.register_type == "project", GovernedRecord.code == entry["code"]))
        if exists:
            result["skipped"].append(entry["code"])
            continue
        data = validate_data("project", entry["data"])
        result["created"].append(entry["code"])
        if dry_run:
            continue
        row = GovernedRecord(organization_id=org_id, register_type="project", code=entry["code"], title=entry["title"], summary=entry["summary"],
                             owner_subject=owner, data=data, created_by=owner, updated_by=owner)
        session.add(row)
        session.flush()
        session.add(AuditEvent(organization_id=org_id, actor_id=owner, action="register_record.seeded", entity_type="register:project",
                               entity_id=row.id, details={"code": entry["code"], "source": "ecosystem-registry.v1"}))
    if not dry_run:
        session.commit()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--org-id", help="organization (org_id claim) that owns the records; defaults to the registry orgId")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--database-url", help="defaults to ASAA_AP_DATABASE_URL")
    parser.add_argument("--owner-subject", default=DEFAULT_OWNER)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.database_url and urlparse(args.database_url.replace("postgresql+psycopg://", "postgresql://", 1)).password:
        print("Refusing a database URL that embeds a password (it would land in shell history and process lists): "
              "use PGPASSWORD or the ASAA_AP_DATABASE_URL environment variable.", file=sys.stderr)
        return 2
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        if registry.get("schema") != "asaa.ecosystem-registry.v1":
            raise ValueError("not an asaa.ecosystem-registry.v1 file")
    except (OSError, ValueError) as exc:
        print(f"Cannot read the ecosystem registry: {exc}", file=sys.stderr)
        return 2
    org_id = args.org_id or registry.get("orgId")
    if not org_id:
        print("No org id: pass --org-id (the registry has no orgId).", file=sys.stderr)
        return 2
    from asaa_ap.database import build_session_factory
    engine, factory = build_session_factory(args.database_url)
    with factory() as session:
        result = seed(session, org_id, registry, args.owner_subject, args.dry_run)
    engine.dispose()
    prefix = "[dry run] would create" if args.dry_run else "created"
    print(f"{prefix}: {', '.join(result['created']) or '-'}; already present: {', '.join(result['skipped']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
