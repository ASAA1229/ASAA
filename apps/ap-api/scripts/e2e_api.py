#!/usr/bin/env python
"""Throw-away API for browser E2E tests (Playwright). Local/CI only: fresh SQLite database, generated RS256 key,
no external services. Writes bearer tokens for test principals to --token-file (JSON) before serving.

  python scripts/e2e_api.py --port 8765 --cors-origin http://127.0.0.1:4173 --token-file ../../.e2e/tokens.json
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUER, AUDIENCE = "https://e2e.invalid", "asaa-e2e"

ADMIN_PERMISSIONS = [
    "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:receipt:read", "ar:receipt:write",
    "authorization:assignment:read", "authorization:role:read", "authorization:role:write",
    "supplier:read", "supplier:write", "supplier:status", "supplier:verify", "procurement:request:read", "procurement:request:write",
    "hr:employee:read", "hr:employee:write", "hr:employment:write", "hr:leave:read", "hr:leave:request", "hr:leave:review",
    "hr:exit:read", "hr:asset:read", "hr:document:read", "onboarding:read",
    "organization:profile:read", "organization:profile:write", "organization:structure:read", "organization:structure:write",
    "masterdata:domain:read", "masterdata:domain:write", "masterdata:record:read",
    "payroll:read", "payroll:compensation:read", "payroll:compensation:write", "payroll:period:write", "payroll:run:write",
    "tms:timesheet:read", "tms:timesheet:write", "tms:timesheet:submit", "expense:claim:read", "expense:claim:write", "audit:read",
]
READER_PERMISSIONS = ["supplier:read"]
from asaa_registers.catalog import TYPES as _REGISTER_CATALOG  # noqa: E402

REGISTER_TYPES = list(_REGISTER_CATALOG)
ADMIN_PERMISSIONS += [f"register:{t}:{a}" for t in REGISTER_TYPES for a in ("read", "write")] + ["governance:delegation:read", "governance:delegation:create", "governance:decision:read", "governance:decision:create", "notification:template:read", "notification:outbox:read", "notification:template:write", "notification:send"]
REVIEWER_PERMISSIONS = [f"register:{t}:{a}" for t in REGISTER_TYPES for a in ("read", "review")] + ["governance:delegation:read", "governance:delegation:approve", "governance:decision:read", "governance:decision:approve"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--cors-origin", default="http://127.0.0.1:4173")
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()

    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    now = datetime.now(timezone.utc)

    def token(subject, permissions):
        return jwt.encode({"sub": subject, "name": subject, "org_id": "e2e-org", "iss": ISSUER, "aud": AUDIENCE, "iat": now,
                           "exp": now + timedelta(hours=4), "permissions": permissions}, key, algorithm="RS256")

    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    args.token_file.write_text(json.dumps({"admin": token("e2e-admin", ADMIN_PERMISSIONS), "reader": token("e2e-reader", READER_PERMISSIONS),
                                           "reviewer": token("e2e-reviewer", REVIEWER_PERMISSIONS)}))

    tmp = tempfile.mkdtemp(prefix="asaa-e2e-")
    env = {**os.environ, "ASAA_AP_DATABASE_URL": f"sqlite:///{Path(tmp, 'e2e.db').as_posix()}", "ASAA_AP_ENVIRONMENT": "test",
           "ASAA_AP_JWT_PUBLIC_KEY": public, "ASAA_AP_JWT_ISSUER": ISSUER, "ASAA_AP_JWT_AUDIENCE": AUDIENCE,
           "ASAA_AP_CORS_ORIGINS": json.dumps([args.cors_origin]), "ASAA_AP_LOG_LEVEL": "WARNING"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
    return subprocess.call([sys.executable, "-m", "uvicorn", "asaa_ap.main:app", "--host", "127.0.0.1", "--port", str(args.port),
                            "--log-level", "warning"], cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
