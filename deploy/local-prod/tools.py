"""Helpers for the LOCAL production deployment (no network calls, nothing leaves this machine).

  ensure-db   create the application database if missing (admin password from PGPASSWORD, never stored)
  tighten     run as the migrator after `alembic upgrade`: make audit_events append-only and alembic_version read-only for the runtime role
  keygen      write an RSA key pair for the portal login tokens (private key stays in the given directory)
  mint        print a signed access token carrying every permission the API knows (owner/admin use on this machine only)
Run with a Python that has psycopg, cryptography and PyJWT (the setup script builds .local-prod/venv with them).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def conn_args(url: str) -> dict:
    p = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    return {"host": p.hostname or "localhost", "port": p.port or 5432, "user": unquote(p.username or ""),
            "password": unquote(p.password) if p.password else os.environ.get("PGPASSWORD"), "dbname": p.path.lstrip("/") or "postgres", "connect_timeout": 10}


def ident(value: str) -> str:
    if not IDENT.match(value):
        raise SystemExit(f"unsafe identifier: {value!r}")
    return '"' + value + '"'


def ensure_db(args) -> int:
    import psycopg
    with psycopg.connect(**{**conn_args(args.admin_url), "dbname": "postgres"}, autocommit=True) as db:
        if db.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args.name,)).fetchone():
            print(f"database {args.name} already exists")
        else:
            db.execute(f"CREATE DATABASE {ident(args.name)} ENCODING 'UTF8'")
            print(f"database {args.name} created")
    return 0


def tighten(args) -> int:
    import psycopg
    runtime = ident(args.runtime)
    with psycopg.connect(**conn_args(args.migrator_url), autocommit=True) as db:
        db.execute(f"REVOKE ALL ON alembic_version FROM {runtime}")
        db.execute(f"GRANT SELECT ON alembic_version TO {runtime}")
        db.execute(f"REVOKE ALL ON audit_events FROM {runtime}")
        db.execute(f"GRANT SELECT, INSERT ON audit_events TO {runtime}")
    print("alembic_version is read-only and audit_events is append-only for", args.runtime)
    return 0


def keygen(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    private_path, public_path = out / "jwt_private.pem", out / "jwt_public.pem"
    if private_path.exists() and not args.force:
        print("key pair already exists (use --force to rotate; existing tokens stop working)")
        return 0
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    print("key pair written to", out)
    return 0


def all_permissions() -> list[str]:
    sys.path.insert(0, str(ROOT / "apps" / "ap-api" / "src"))
    found: set[str] = set()
    pattern = re.compile(r"[\"']([a-z_]+(?::[a-z_*]+){1,3})[\"']")
    for path in (ROOT / "apps" / "ap-api" / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for call in re.finditer(r"(?:require_permission|require_any)\(([^)]*)\)", text):
            found.update(m.group(1) for m in pattern.finditer(call.group(1)))
        found.update(m.group(1) for m in re.finditer(r"[\"']([a-z_]+(?::[a-z_]+){1,3}:(?:read|write|review|approve|submit|issue|allocate|reimburse|all|manage))[\"']", text))
    from asaa_registers.catalog import TYPES
    found.update(f"register:{t}:{a}" for t in TYPES for a in ("read", "write", "review"))
    return sorted(found)


def mint(args) -> int:
    import jwt
    key = Path(args.key).read_text()
    now = datetime.now(timezone.utc)
    permissions = [p for p in args.permissions.split(",") if p] if args.permissions else all_permissions()
    token = jwt.encode({"sub": args.subject, "org_id": args.org, "iss": args.issuer, "aud": args.audience, "iat": now, "exp": now + timedelta(hours=args.hours),
                        "permissions": permissions}, key, algorithm="RS256")
    print(token)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("ensure-db"); e.add_argument("--admin-url", required=True); e.add_argument("--name", required=True); e.set_defaults(fn=ensure_db)
    t = sub.add_parser("tighten"); t.add_argument("--migrator-url", required=True); t.add_argument("--runtime", required=True); t.set_defaults(fn=tighten)
    k = sub.add_parser("keygen"); k.add_argument("--out-dir", required=True); k.add_argument("--force", action="store_true"); k.set_defaults(fn=keygen)
    m = sub.add_parser("mint"); m.add_argument("--key", required=True); m.add_argument("--subject", default="local-owner")
    m.add_argument("--org", default="asaa-local"); m.add_argument("--issuer", default="https://asaa.local.invalid"); m.add_argument("--audience", default="asaa-local-prod")
    m.add_argument("--hours", type=float, default=8); m.add_argument("--permissions", default=""); m.set_defaults(fn=mint)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
