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

Encryption at rest (AES-256-GCM, authenticated chunks): --encrypt-key-file takes a file path or `env:VARIABLE` holding a
base64 32-byte key (`python scripts/backup_restore.py keygen`). Scheduled operation:
  python scripts/backup_restore.py scheduled --database-url ... --out backups/ --encrypt-key-file env:ASAA_BACKUP_KEY
  python scripts/backup_restore.py check-staleness --out backups/ --max-age-hours 26     # exit 2 = stale/failed (alert)
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


def strip_newer_pg_restore_settings(source: Path, target: Path) -> None:
    """Remove session settings emitted by newer pg_dump clients but unknown to older servers.

    PostgreSQL 17+ clients emit SET transaction_timeout = 0; PostgreSQL 16 rejects it.
    Keep the archive itself intact and filter only this nonessential session setting from
    the generated restore SQL before executing it with psql.
    """
    with source.open("r", encoding="utf-8") as input_file, target.open("w", encoding="utf-8", newline="") as output_file:
        for line in input_file:
            if line.strip().lower() == "set transaction_timeout = 0;":
                continue
            output_file.write(line)


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

MAGIC = b"ASAAGCM1"
FRAME = 1024 * 1024


def _load_key(source: str) -> bytes:
    """Key material: 32 random bytes, base64 encoded, from a file path or `env:VARIABLE`."""
    import base64
    raw = os.environ.get(source[4:]) if source.startswith("env:") else Path(source).read_text()
    if not raw or not raw.strip():
        raise BackupError("Backup encryption key not found (empty environment variable or file)")
    text = raw.strip()
    try:
        key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except Exception as exc:
        raise BackupError("Backup encryption key must be base64") from exc
    if len(key) != 32:
        raise BackupError("Backup encryption key must decode to exactly 32 bytes (AES-256)")
    return key


def generate_key() -> str:
    import base64
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _aad(index: int, final: bool) -> bytes:
    return index.to_bytes(8, "big") + (b"\x01" if final else b"\x00")


def _crypt(src: Path, dst: Path, key_source: str, encrypt: bool) -> None:
    """AES-256-GCM in 1 MiB frames with a random nonce each. Frame index and a final-frame flag are authenticated, so
    frames cannot be reordered or dropped and the file cannot be truncated without detection."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes = AESGCM(_load_key(key_source))
    with src.open("rb") as fin, dst.open("wb") as fout:
        if encrypt:
            fout.write(MAGIC)
            block, index = fin.read(FRAME), 0
            while True:
                following = fin.read(FRAME)
                final = not following
                nonce = os.urandom(12)
                sealed = aes.encrypt(nonce, block, _aad(index, final))
                fout.write(len(sealed).to_bytes(4, "big") + nonce + sealed)
                if final:
                    return
                block, index = following, index + 1
        if fin.read(len(MAGIC)) != MAGIC:
            raise BackupError("Not an encrypted ASAA backup (bad header)")
        index = 0
        while True:
            header = fin.read(4)
            if not header:
                raise BackupError("Encrypted backup is truncated")
            size = int.from_bytes(header, "big")
            nonce, sealed = fin.read(12), fin.read(size)
            if len(nonce) != 12 or len(sealed) != size:
                raise BackupError("Encrypted backup is truncated")
            final = not fin.peek(1)[:1]
            try:
                fout.write(aes.decrypt(nonce, sealed, _aad(index, final)))
            except InvalidTag as exc:
                raise BackupError("Backup could not be decrypted (wrong key, tampering or truncation)") from exc
            if final:
                return
            index += 1


def encrypt_file(path: Path, key_source: str) -> Path:
    target = path.with_name(path.name + ".enc")
    _crypt(path, target, key_source, True)
    path.unlink()
    return target


def decrypt_to_temp(path: Path, key_source: str) -> Path:
    handle, name = tempfile.mkstemp(suffix=".plain")
    os.close(handle)
    try:
        _crypt(path, Path(name), key_source, False)
    except BackupError:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


# ---------- retention, scheduling, staleness ---------------------------------

def _manifests(out_dir: Path) -> list[tuple[datetime, Path, dict]]:
    found = []
    for manifest_path in out_dir.glob("asaa-*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
            found.append((datetime.fromisoformat(manifest["created_at"]), out_dir / manifest["artifact"], manifest))
        except (ValueError, KeyError, OSError):
            continue
    return sorted(found, key=lambda item: item[0], reverse=True)


def rotate(out_dir: Path, keep_daily: int = 7, keep_weekly: int = 4, keep_monthly: int = 6) -> dict:
    """Grandfather-father-son retention: newest backup per day (last N days), per ISO week and per month.
    The newest backup is always kept."""
    entries = _manifests(out_dir)
    keep: set[Path] = set()
    seen: dict[str, set] = {"d": set(), "w": set(), "m": set()}
    limits = {"d": keep_daily, "w": keep_weekly, "m": keep_monthly}
    for created, artifact, _ in entries:  # newest first
        keys = {"d": created.strftime("%Y-%m-%d"), "w": "%d-W%02d" % created.isocalendar()[:2], "m": created.strftime("%Y-%m")}
        for kind, key in keys.items():
            if key not in seen[kind] and len(seen[kind]) < limits[kind]:
                seen[kind].add(key)
                keep.add(artifact)
    if entries:
        keep.add(entries[0][1])
    deleted = []
    for _, artifact, _ in entries:
        if artifact not in keep:
            artifact.unlink(missing_ok=True)
            artifact.with_name(artifact.name + ".manifest.json").unlink(missing_ok=True)
            deleted.append(artifact.name)
    return {"kept": sorted(a.name for a in keep), "deleted": sorted(deleted)}


STATUS_FILE = "backup-status.json"


def scheduled(url: str, out_dir: Path, key_source: str | None, keep: tuple[int, int, int] = (7, 4, 6)) -> dict:
    """One scheduled run: backup -> verify -> rotate -> record status. Old backups are only pruned after the new one verified."""
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / STATUS_FILE
    previous = json.loads(status_path.read_text()) if status_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    try:
        artifact = backup(url, out_dir, key_source)
        manifest = verify_backup(artifact, key_source)
        retention = rotate(out_dir, *keep)
        status = {**previous, "last_success_at": now, "last_artifact": artifact.name, "last_error": None,
                  "sha256": manifest["sha256"], "retention": retention}
    except (BackupError, subprocess.CalledProcessError, OSError) as exc:
        status = {**previous, "last_failure_at": now, "last_error": str(exc)[:300]}
        status_path.write_text(json.dumps(status, indent=2))
        raise
    status_path.write_text(json.dumps(status, indent=2))
    return status


def check_staleness(out_dir: Path, max_age_hours: float, now: datetime | None = None) -> dict:
    """Monitoring check: not ok when no verified backup exists, the last run failed after the last success,
    the newest backup is older than max_age_hours, or the recorded artifact is missing."""
    now = now or datetime.now(timezone.utc)
    status_path = out_dir / STATUS_FILE
    result = {"ok": False, "reason": None, "age_hours": None}
    if not status_path.exists():
        result["reason"] = "no backup status recorded"
        return result
    status = json.loads(status_path.read_text())
    if not status.get("last_success_at"):
        result["reason"] = "no successful backup recorded"
        return result
    age = (now - datetime.fromisoformat(status["last_success_at"])).total_seconds() / 3600
    result["age_hours"] = round(age, 2)
    if status.get("last_failure_at") and status["last_failure_at"] > status["last_success_at"]:
        result["reason"] = "last backup run failed: " + str(status.get("last_error"))
    elif age > max_age_hours:
        result["reason"] = f"newest backup is {age:.1f}h old (limit {max_age_hours}h)"
    elif not (out_dir / status.get("last_artifact", "")).exists():
        result["reason"] = "recorded backup artifact is missing"
    else:
        result["ok"] = True
    return result


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
            # Render the archive to SQL first so a newer pg_dump/pg_restore client can
            # target an older PostgreSQL server (e.g. PG18 client -> PG16 target).
            with tempfile.TemporaryDirectory(prefix="asaa-pg-restore-") as work_dir:
                raw_sql = Path(work_dir) / "restore.sql"
                compatible_sql = Path(work_dir) / "restore-compatible.sql"
                command = [find_tool("pg_restore"), "--no-owner", "--no-privileges", "--file", str(raw_sql)]
                if force:
                    command[1:1] = ["--clean", "--if-exists"]
                subprocess.run([*command, str(plain)], check=True, capture_output=True, text=True)
                strip_newer_pg_restore_settings(raw_sql, compatible_sql)
                psql = [find_tool("psql"), "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--single-transaction",
                        "-h", parts["host"], "-p", parts["port"], "-U", parts["user"], "-d", parts["dbname"],
                        "--file", str(compatible_sql)]
                subprocess.run(psql, check=True, capture_output=True, text=True)
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
    sub.add_parser("keygen")
    sc = sub.add_parser("scheduled")
    sc.add_argument("--database-url", default=os.environ.get("ASAA_AP_DATABASE_URL", "sqlite:///./asaa_ap.db"))
    sc.add_argument("--out", type=Path, default=Path("backups"))
    sc.add_argument("--encrypt-key-file")
    sc.add_argument("--keep-daily", type=int, default=7)
    sc.add_argument("--keep-weekly", type=int, default=4)
    sc.add_argument("--keep-monthly", type=int, default=6)
    st = sub.add_parser("check-staleness")
    st.add_argument("--out", type=Path, default=Path("backups"))
    st.add_argument("--max-age-hours", type=float, default=26)
    ro = sub.add_parser("rotate")
    ro.add_argument("--out", type=Path, default=Path("backups"))
    ro.add_argument("--keep-daily", type=int, default=7)
    ro.add_argument("--keep-weekly", type=int, default=4)
    ro.add_argument("--keep-monthly", type=int, default=6)
    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            print(generate_key())
            return 0
        if args.command == "check-staleness":
            result = check_staleness(args.out, args.max_age_hours)
            print(json.dumps(result))
            return 0 if result["ok"] else 2
        if args.command == "rotate":
            print(json.dumps(rotate(args.out, args.keep_daily, args.keep_weekly, args.keep_monthly)))
            return 0
        if args.command == "scheduled":
            status = scheduled(args.database_url, args.out, args.encrypt_key_file, (args.keep_daily, args.keep_weekly, args.keep_monthly))
            print(json.dumps({k: status[k] for k in ("last_success_at", "last_artifact", "sha256")}))
            return 0
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
