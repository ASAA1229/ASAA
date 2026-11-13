#!/usr/bin/env python
"""PostgreSQL role separation: provision least-privilege roles and verify them (ASAA-004 / ASAA-001).

  provision  Run as an administrative role. Creates (if missing) a migration role that owns the schema
             objects and a runtime role that can only read/write rows. Idempotent; re-run after every migration
             so grants cover new tables. Passwords come from the environment, never the command line:
               ASAA_DB_MIGRATOR_PASSWORD, ASAA_DB_RUNTIME_PASSWORD
  check      Run as the RUNTIME role (URL without password; PGPASSWORD). Asserts it cannot change the schema
             or the migration history and cannot tamper with audit rows, by actually attempting the forbidden
             statements inside rolled-back transactions. Exit code 1 if any check fails.

Policy applied to the runtime role
  * no superuser/createdb/createrole/replication/bypassrls, no CREATE on the schema, owns no tables
  * SELECT/INSERT/UPDATE/DELETE on application tables, except:
      - alembic_version: SELECT only (no migration-history writes)
      - audit_events: SELECT and INSERT only (append-only; no UPDATE/DELETE/TRUNCATE)
  * USAGE/SELECT on sequences; no TRUNCATE, REFERENCES or TRIGGER anywhere

Whether this matches the approved production role matrix is an owner/DBA decision; this is the baseline the
repository enforces and tests locally. It is not evidence about any production database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import unquote, urlparse

import psycopg
from psycopg import sql

APPEND_ONLY = ("audit_events",)
HISTORY = ("alembic_version",)
IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def parse(url: str) -> dict:
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    return {"host": parsed.hostname or "localhost", "port": parsed.port or 5432, "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password) if parsed.password else os.environ.get("PGPASSWORD"),
            "dbname": parsed.path.lstrip("/")}


def ident(value: str) -> sql.Identifier:
    if not IDENT.match(value):
        raise SystemExit(f"unsafe identifier: {value!r}")
    return sql.Identifier(value)


def provision(admin_url: str, migrator: str, runtime: str, schema: str = "public") -> dict:
    migrator_pw, runtime_pw = os.environ.get("ASAA_DB_MIGRATOR_PASSWORD"), os.environ.get("ASAA_DB_RUNTIME_PASSWORD")
    if not migrator_pw or not runtime_pw:
        raise SystemExit("Set ASAA_DB_MIGRATOR_PASSWORD and ASAA_DB_RUNTIME_PASSWORD in the environment")
    conn_args = parse(admin_url)
    with psycopg.connect(**conn_args, autocommit=True) as db:
        for role, password in ((migrator, migrator_pw), (runtime, runtime_pw)):
            exists = db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            db.execute(sql.SQL(f"{verb} ROLE {{}} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {{}}").format(
                ident(role), sql.Literal(password)))
        dbname = conn_args["dbname"]
        db.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(ident(dbname)))
        db.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(ident(dbname), ident(migrator), ident(runtime)))
        db.execute(sql.SQL("REVOKE CREATE ON SCHEMA {} FROM PUBLIC").format(ident(schema)))
        db.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(ident(schema), ident(migrator)))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(ident(schema), ident(runtime)))
        # Existing objects: hand ownership to the migration role so only it can alter them.
        tables = [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,))]
        sequences = [r[0] for r in db.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = %s", (schema,))]
        for table in tables:
            db.execute(sql.SQL("ALTER TABLE {}.{} OWNER TO {}").format(ident(schema), sql.Identifier(table), ident(migrator)))
        for sequence in sequences:
            db.execute(sql.SQL("ALTER SEQUENCE {}.{} OWNER TO {}").format(ident(schema), sql.Identifier(sequence), ident(migrator)))
        # Grants (idempotent: revoke then grant).
        db.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(ident(schema), ident(runtime)))
        db.execute(sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA {} FROM {}").format(ident(schema), ident(runtime)))
        for table in tables:
            if table in HISTORY:
                privileges = "SELECT"
            elif table in APPEND_ONLY:
                privileges = "SELECT, INSERT"
            else:
                privileges = "SELECT, INSERT, UPDATE, DELETE"
            db.execute(sql.SQL(f"GRANT {privileges} ON {{}}.{{}} TO {{}}").format(ident(schema), sql.Identifier(table), ident(runtime)))
        db.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(ident(schema), ident(runtime)))
        # Future tables created by the migration role are readable/writable by runtime; re-run provision to tighten
        # alembic_version/audit-style tables after the next migration.
        db.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(
            ident(migrator), ident(schema), ident(runtime)))
        db.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT USAGE, SELECT ON SEQUENCES TO {}").format(
            ident(migrator), ident(schema), ident(runtime)))
    return {"provisioned": True, "tables": len(tables), "migrator": migrator, "runtime": runtime}


def _attempt(db, statement: str) -> str | None:
    """Run a forbidden statement in a transaction that is always rolled back; return the error class if it was refused."""
    try:
        with db.transaction(force_rollback=True):
            db.execute(statement)
        return None
    except psycopg.errors.InsufficientPrivilege:
        return "InsufficientPrivilege"
    except psycopg.errors.Error as exc:  # any other refusal still proves the change did not apply, but is not the intended control
        return type(exc).__name__


def check(runtime_url: str, schema: str = "public") -> dict:
    conn_args = parse(runtime_url)
    checks: list[dict] = []

    def record(name, passed, detail=""):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    with psycopg.connect(**conn_args, autocommit=True) as db:
        role = db.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
        record("role_has_no_elevated_attributes", role is not None and not any(role), "superuser/createdb/createrole/replication/bypassrls all false")
        record("no_schema_create", not db.execute("SELECT has_schema_privilege(current_user, %s, 'CREATE')", (schema,)).fetchone()[0])
        owned = [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s AND tableowner = current_user", (schema,))]
        record("owns_no_tables", not owned, ", ".join(owned))
        tables = [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY 1", (schema,))]
        app_tables = [t for t in tables if t not in HISTORY]
        missing = [f"{t}:{p}" for t in app_tables for p in ("SELECT", "INSERT") if not db.execute("SELECT has_table_privilege(current_user, %s, %s)", (f'"{schema}"."{t}"', p)).fetchone()[0]]
        record("dml_on_application_tables", not missing, ", ".join(missing[:5]))
        dangerous = []
        for t in tables:
            for privilege in ("TRUNCATE", "REFERENCES", "TRIGGER"):
                if db.execute("SELECT has_table_privilege(current_user, %s, %s)", (f'"{schema}"."{t}"', privilege)).fetchone()[0]:
                    dangerous.append(f"{t}:{privilege}")
        record("no_truncate_references_trigger", not dangerous, ", ".join(dangerous[:5]))
        for t in HISTORY:
            if t in tables:
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    record(f"{t}_{privilege.lower()}_denied", not db.execute("SELECT has_table_privilege(current_user, %s, %s)", (f'"{schema}"."{t}"', privilege)).fetchone()[0])
                record(f"{t}_write_attempt_refused", _attempt(db, f"UPDATE {t} SET version_num = version_num") == "InsufficientPrivilege")
        for t in APPEND_ONLY:
            if t in tables:
                for privilege in ("UPDATE", "DELETE"):
                    record(f"{t}_{privilege.lower()}_denied", not db.execute("SELECT has_table_privilege(current_user, %s, %s)", (f'"{schema}"."{t}"', privilege)).fetchone()[0])
                record(f"{t}_delete_attempt_refused", _attempt(db, f"DELETE FROM {t}") == "InsufficientPrivilege")
        record("create_table_refused", _attempt(db, "CREATE TABLE asaa_priv_probe (id int)") == "InsufficientPrivilege")
        if app_tables:
            record("drop_table_refused", _attempt(db, f'DROP TABLE "{app_tables[0]}"') == "InsufficientPrivilege")
            record("alter_table_refused", _attempt(db, f'ALTER TABLE "{app_tables[0]}" ADD COLUMN asaa_probe int') == "InsufficientPrivilege")
            record("truncate_refused", _attempt(db, f'TRUNCATE "{app_tables[0]}"') == "InsufficientPrivilege")
    failed = [c for c in checks if not c["passed"]]
    return {"status": "passed" if not failed else "failed", "database_url": "redacted", "checks": checks}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("provision")
    p.add_argument("--admin-url", required=True)
    p.add_argument("--migrator", default="asaa_migrator")
    p.add_argument("--runtime", default="asaa_runtime")
    c = sub.add_parser("check")
    c.add_argument("--runtime-url", default=os.environ.get("ASAA_AP_DATABASE_URL"))
    args = parser.parse_args(argv)
    if args.command == "provision":
        print(json.dumps(provision(args.admin_url, args.migrator, args.runtime)))
        return 0
    result = check(args.runtime_url)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
