#!/usr/bin/env python
"""Backup, restore and integrity verification for the ASAA database (ASAA-005).

Supports SQLite (local/dev) and PostgreSQL (pg_dump custom format / pg_restore).
Every backup is accompanied by a JSON manifest holding a SHA-256 checksum, the Alembic
revision and per-table row counts. `verify` re-checks the artifact; `restore --verify`
restores into a target and proves the restored data matches the manifest.

Examples
  python scripts/backup_restore.py backup  --database-url sqlite:///./asaa_ap.db --out backups/
  python scripts/backup_restore.py verify  --backup backups/asaa-20261113T101500Z.sqlite
  python scripts/backup_restore.py restore --backup backups/asaa-....sqlite --database-url sqlite:///./restored.db --verify
  python scripts/backup_restore.py backup  --database-url postgresql://user@host/db --out backups/   (PGPASSWORD from env)
  python scripts/backup_restore.py restore --backup backups/asaa-....dump --database-url postgresql://user@host/restore_db --verify

Optional encryption at rest: --encrypt-key-file points to a file holding a Fernet key
(`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Key custody, off-site storage, retention and RPO/RTO values are owner decisions and are NOT
configured here. Passwords are never accepted on the command line; use PGPASSWORD/.pgpass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

CHUNK = 1024 * 1024


class BackupError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def is_postgres(url: str) -> bool:
    return url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://"))


def sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise BackupError("Only sqlite:///path URLs are supported for SQLite")
    return Path(unquote(url.removeprefix("sqlite:///")))


def pg_parts(url: str) -> dict:
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    if parsed.password:
        raise BackupError("Do not embed a password in the database URL; set PGPASSWORD or use .pgpass")
    return {"host": parsed.hostname or "localhost", "port": str(parsed.port or 5432),
            "user": unquote(parsed.username or ""), "dbname": parsed.path.lstrip("/")}


def find_tool(name: str) -> str:
    override = os.environ.get(f"ASAA_{name.upper()}_BIN")
    if override:
        return override
    found = shutil.which(name)
    if found:
        return found
    for base in sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin"), reverse=True) if os.name == "nt" else []:
        candidate = base / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    raise BackupError(f"{name} not found on PATH (set ASAA_{name.upper()}_BIN)")


# ---------- table statistics -------------------------------------------------

def sqlite_stats(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BackupError("SQLite integrity_check failed")
        tables = [r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = {t: connection.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        revision = None
        if "alembic_version" in tables:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            revision = row[0] if row else None
        return {"tables": counts, "alembic_revision": revision}
    finally:
        connection.close()


def pg_stats(url: str) -> dict:
    import psycopg
    parts = pg_parts(url)
    with psycopg.connect(host=parts["host"], port=int(parts["port"]), user=parts["user"], dbname=parts["dbname"],
                         password=os.environ.get("PGPASSWORD")) as connection:
        tables = [r[0] for r in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        counts = {}
        for table in tables:
            counts[table] = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        revision = None
        if "alembic_version" in tables:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            revision = row[0] if row else None
        return {"tables": counts, "alembic_revision": revision}


def stats_for(url: str) -> dict:
    return pg_stats(url) if is_postgres(url) else sqlite_stats(sqlite_path(url))


# ---------- encryption -------------------------------------------------------

def _fernet(key_file: str):
    from cryptography.fernet import Fernet
    return Fernet(Path(key_file).read_bytes().strip())


def encrypt_file(path: Path, key_file: str) -> Path:
    target = path.with_name(path.name + ".enc")
    target.write_bytes(_fernet(key_file).encrypt(path.read_bytes()))
    path.unlink()
    return target


def decrypt_to_temp(path: Path, key_file: str) -> Path:
    handle, name = tempfile.mkstemp(suffix=".plain")
    os.close(handle)
    try:
        Path(name).write_bytes(_fernet(key_file).decrypt(path.read_bytes()))
    except Exception as exc:  # InvalidToken etc.
        Path(name).unlink(missing_ok=True)
        raise BackupError("Backup could not be decrypted (wrong key or corrupted file)") from exc
    return Path(name)


# ---------- operations -------------------------------------------------------

def backup(url: str, out_dir: Path, encrypt_key_file: str | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = time.perf_counter()
    if is_postgres(url):
        artifact = out_dir / f"asaa-{stamp}.dump"
        parts = pg_parts(url)
        subprocess.run([find_tool("pg_dump"), "-Fc", "--no-owner", "--no-privileges", "-h", parts["host"], "-p", parts["port"],
                        "-U", parts["user"], "-f", str(artifact), parts["dbname"]], check=True, capture_output=True, text=True)
        kind = "postgresql"
    else:
        source = sqlite_path(url)
        if not source.exists():
            raise BackupError(f"SQLite database not found: {source}")
        artifact = out_dir / f"asaa-{stamp}.sqlite"
        src = sqlite3.connect(source)
        dst = sqlite3.connect(artifact)
        try:
            src.backup(dst)  # consistent online copy
        finally:
            dst.close()
            src.close()
        kind = "sqlite"
    stats = stats_for(url)
    encrypted = False
    if encrypt_key_file:
        artifact = encrypt_file(artifact, encrypt_key_file)
        encrypted = True
    manifest = {
        "format": 1, "kind": kind, "artifact": artifact.name, "encrypted": encrypted,
        "created_at": datetime.now(timezone.utc).isoformat(), "sha256": sha256_of(artifact),
        "size_bytes": artifact.stat().st_size, "duration_seconds": round(time.perf_counter() - started, 3), **stats,
    }
    manifest_path = artifact.with_name(artifact.name + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return artifact


def load_manifest(artifact: Path) -> dict:
    manifest_path = artifact.with_name(artifact.name + ".manifest.json")
    if not manifest_path.exists():
        raise BackupError(f"Manifest missing: {manifest_path}")
    return json.loads(manifest_path.read_text())


def verify_backup(artifact: Path, encrypt_key_file: str | None = None) -> dict:
    """Check the artifact against its manifest: checksum always; SQLite content/row counts when readable."""
    if not artifact.exists():
        raise BackupError(f"Backup not found: {artifact}")
    manifest = load_manifest(artifact)
    actual = sha256_of(artifact)
    if actual != manifest["sha256"]:
        raise BackupError(f"Checksum mismatch (expected {manifest['sha256'][:12]}..., got {actual[:12]}...)")
    if artifact.stat().st_size != manifest["size_bytes"]:
        raise BackupError("Size mismatch")
    if manifest["kind"] == "sqlite":
        plain, cleanup = artifact, None
        if manifest["encrypted"]:
            if not encrypt_key_file:
                raise BackupError("Encrypted backup: --encrypt-key-file required to verify contents")
            plain = cleanup = decrypt_to_temp(artifact, encrypt_key_file)
        try:
            if sqlite_stats(plain)["tables"] != manifest["tables"]:
                raise BackupError("Row counts in backup differ from manifest")
        finally:
            if cleanup:
                cleanup.unlink(missing_ok=True)
    else:
        if manifest["encrypted"] and not encrypt_key_file:
            raise BackupError("Encrypted backup: --encrypt-key-file required to verify contents")
        plain, cleanup = artifact, None
        if manifest["encrypted"]:
            plain = cleanup = decrypt_to_temp(artifact, encrypt_key_file)
        try:  # pg_restore --list parses the archive TOC: detects truncated/corrupt custom-format dumps
            subprocess.run([find_tool("pg_restore"), "--list", str(plain)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise BackupError("pg_restore could not read the archive: " + exc.stderr.strip()[:200]) from exc
        finally:
            if cleanup:
                cleanup.unlink(missing_ok=True)
    return manifest


def restore(artifact: Path, url: str, encrypt_key_file: str | None = None, verify: bool = True, force: bool = False) -> dict:
    manifest = verify_backup(artifact, encrypt_key_file)
    started = time.perf_counter()
    plain, cleanup = artifact, None
    if manifest["encrypted"]:
        plain = cleanup = decrypt_to_temp(artifact, encrypt_key_file)
    try:
        if manifest["kind"] == "postgresql":
            if not is_postgres(url):
                raise BackupError("PostgreSQL backup requires a PostgreSQL target URL")
            parts = pg_parts(url)
            command = [find_tool("pg_restore"), "--no-owner", "--no-privileges", "--exit-on-error", "-h", parts["host"],
                       "-p", parts["port"], "-U", parts["user"], "-d", parts["dbname"]]
            if force:
                command.insert(1, "--clean")
                command.insert(2, "--if-exists")
            subprocess.run([*command, str(plain)], check=True, capture_output=True, text=True)
        else:
            if is_postgres(url):
                raise BackupError("SQLite backup requires a sqlite:/// target URL")
            target = sqlite_path(url)
            if target.exists() and not force:
                raise BackupError(f"Refusing to overwrite existing {target}; pass --force")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plain, target)
    except subprocess.CalledProcessError as exc:
        raise BackupError("pg_restore failed: " + exc.stderr.strip()[:300]) from exc
    finally:
        if cleanup:
            cleanup.unlink(missing_ok=True)
    elapsed = round(time.perf_counter() - started, 3)
    result = {"restore_seconds": elapsed, "backup": manifest["artifact"], "verified": False}
    if verify:
        restored = stats_for(url)
        if restored["tables"] != manifest["tables"]:
            diff = {t: (manifest["tables"].get(t), restored["tables"].get(t))
                    for t in set(manifest["tables"]) | set(restored["tables"]) if manifest["tables"].get(t) != restored["tables"].get(t)}
            raise BackupError(f"Restored data does not match manifest: {diff}")
        if restored["alembic_revision"] != manifest["alembic_revision"]:
            raise BackupError("Restored Alembic revision differs from manifest")
        result.update(verified=True, tables=len(restored["tables"]), rows=sum(restored["tables"].values()),
                      alembic_revision=restored["alembic_revision"])
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--database-url", default=os.environ.get("ASAA_AP_DATABASE_URL", "sqlite:///./asaa_ap.db"))
    b.add_argument("--out", type=Path, default=Path("backups"))
    b.add_argument("--encrypt-key-file")
    v = sub.add_parser("verify")
    v.add_argument("--backup", type=Path, required=True)
    v.add_argument("--encrypt-key-file")
    r = sub.add_parser("restore")
    r.add_argument("--backup", type=Path, required=True)
    r.add_argument("--database-url", required=True)
    r.add_argument("--encrypt-key-file")
    r.add_argument("--verify", action="store_true")
    r.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            artifact = backup(args.database_url, args.out, args.encrypt_key_file)
            print(json.dumps({"backup": str(artifact), **{k: load_manifest(artifact)[k] for k in ("sha256", "size_bytes", "alembic_revision")}}))
        elif args.command == "verify":
            print(json.dumps({"verified": True, **{k: verify_backup(args.backup, args.encrypt_key_file)[k] for k in ("sha256", "created_at", "alembic_revision")}}))
        else:
            print(json.dumps(restore(args.backup, args.database_url, args.encrypt_key_file, args.verify, args.force)))
    except (BackupError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
