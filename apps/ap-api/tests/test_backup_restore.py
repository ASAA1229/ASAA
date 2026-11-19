"""Local backup -> restore -> verify round trips (ASAA-005). PostgreSQL variant runs only when
ASAA_AP_POSTGRES_TEST_URL and the pg_dump/pg_restore client tools are available."""
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import backup_restore as br  # noqa: E402


def migrate(url: str):
    env = {**os.environ, "ASAA_AP_DATABASE_URL": url, "ASAA_AP_ENVIRONMENT": "development"}
    if url.startswith("postgresql"):
        env["ASAA_AP_ENVIRONMENT"] = "test"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)


@pytest.fixture
def populated_sqlite(tmp_path):
    db = tmp_path / "source.db"
    url = f"sqlite:///{db.as_posix()}"
    migrate(url)
    connection = sqlite3.connect(db)
    now = "2026-11-13 00:00:00"
    for i in range(25):
        connection.execute(
            "INSERT INTO ap_suppliers (id, organization_id, legal_name, normalized_legal_name, status, version, created_at, updated_at, created_by, updated_by) "
            "VALUES (?, 'org-a', ?, ?, 'Draft', 1, ?, ?, 'tester', 'tester')", (str(uuid.uuid4()), f"Supplier {i}", f"supplier {i}", now, now))
    connection.commit()
    connection.close()
    return url, db


def test_sqlite_round_trip_backup_restore_verify(populated_sqlite, tmp_path):
    url, _ = populated_sqlite
    artifact = br.backup(url, tmp_path / "backups")
    manifest = br.verify_backup(artifact)
    assert manifest["tables"]["ap_suppliers"] == 25
    assert manifest["alembic_revision"]  # head revision captured
    target = tmp_path / "restored.db"
    result = br.restore(artifact, f"sqlite:///{target.as_posix()}", verify=True)
    assert result["verified"] is True and result["rows"] >= 25 and result["restore_seconds"] >= 0
    # restored database is a fully functional copy
    restored = sqlite3.connect(target)
    assert restored.execute("SELECT COUNT(*) FROM ap_suppliers WHERE organization_id='org-a'").fetchone()[0] == 25
    restored.close()


def test_backup_is_consistent_while_source_is_written(populated_sqlite, tmp_path):
    url, db = populated_sqlite
    writer = sqlite3.connect(db)
    writer.execute("BEGIN")
    writer.execute("DELETE FROM ap_suppliers WHERE legal_name='Supplier 0'")  # uncommitted change must not appear
    artifact = br.backup(url, tmp_path / "b")
    writer.rollback()
    writer.close()
    assert br.verify_backup(artifact)["tables"]["ap_suppliers"] == 25


def test_corrupted_backup_is_detected(populated_sqlite, tmp_path):
    url, _ = populated_sqlite
    artifact = br.backup(url, tmp_path / "b")
    data = bytearray(artifact.read_bytes())
    data[len(data) // 2] ^= 0xFF
    artifact.write_bytes(bytes(data))
    with pytest.raises(br.BackupError, match="Checksum mismatch"):
        br.verify_backup(artifact)
    with pytest.raises(br.BackupError):
        br.restore(artifact, f"sqlite:///{(tmp_path / 'never.db').as_posix()}")
    assert not (tmp_path / "never.db").exists()


def test_missing_manifest_and_truncated_backup_are_rejected(populated_sqlite, tmp_path):
    url, _ = populated_sqlite
    artifact = br.backup(url, tmp_path / "b")
    artifact.with_name(artifact.name + ".manifest.json").unlink()
    with pytest.raises(br.BackupError, match="Manifest missing"):
        br.verify_backup(artifact)


def test_restore_refuses_to_overwrite_without_force_and_detects_row_count_drift(populated_sqlite, tmp_path):
    url, db = populated_sqlite
    artifact = br.backup(url, tmp_path / "b")
    with pytest.raises(br.BackupError, match="Refusing to overwrite"):
        br.restore(artifact, url)
    assert br.restore(artifact, url, force=True)["verified"] is True


def test_encrypted_backup_round_trip_and_wrong_key(populated_sqlite, tmp_path):
    from cryptography.fernet import Fernet
    url, _ = populated_sqlite
    key_file = tmp_path / "key"
    key_file.write_bytes(Fernet.generate_key())
    other_key = tmp_path / "other"
    other_key.write_bytes(Fernet.generate_key())
    artifact = br.backup(url, tmp_path / "b", encrypt_key_file=str(key_file))
    assert artifact.suffix == ".enc" and b"SQLite format" not in artifact.read_bytes()[:32]
    assert br.verify_backup(artifact, str(key_file))["encrypted"] is True
    with pytest.raises(br.BackupError):
        br.verify_backup(artifact, str(other_key))
    with pytest.raises(br.BackupError, match="key-file required"):
        br.verify_backup(artifact)
    target = tmp_path / "dec.db"
    assert br.restore(artifact, f"sqlite:///{target.as_posix()}", str(key_file))["verified"] is True


def test_cli_exit_codes(populated_sqlite, tmp_path, capsys):
    url, _ = populated_sqlite
    assert br.main(["backup", "--database-url", url, "--out", str(tmp_path / "cli")]) == 0
    artifact = next((tmp_path / "cli").glob("*.sqlite"))
    assert br.main(["verify", "--backup", str(artifact)]) == 0
    artifact.write_bytes(b"tampered")
    assert br.main(["verify", "--backup", str(artifact)]) == 1
    assert "Checksum mismatch" in capsys.readouterr().err


def test_password_in_url_is_refused():
    with pytest.raises(br.BackupError, match="password"):
        br.pg_parts("postgresql://user:secret@host/db")


def test_sqlite_stats_quotes_unusual_table_identifiers(tmp_path):
    db = tmp_path / "quoted-identifiers.db"
    connection = sqlite3.connect(db)
    connection.execute('CREATE TABLE "odd""table name" (id INTEGER)')
    connection.executemany('INSERT INTO "odd""table name" (id) VALUES (?)', [(1,), (2,), (3,)])
    connection.commit()
    connection.close()

    result = br.sqlite_stats(db)

    assert result["tables"]['odd"table name'] == 3


def test_pg_restore_compat_strips_only_newer_server_session_setting(tmp_path):
    source = tmp_path / "restore.sql"
    target = tmp_path / "compatible.sql"
    source.write_text("SET statement_timeout = 0;\nSET transaction_timeout = 0;\nSELECT 1;\n", encoding="utf-8")

    br.strip_newer_pg_restore_settings(source, target)

    assert target.read_text(encoding="utf-8") == "SET statement_timeout = 0;\nSELECT 1;\n"


PG_URL = os.getenv("ASAA_AP_POSTGRES_TEST_URL")


@pytest.mark.skipif(not PG_URL, reason="needs ASAA_AP_POSTGRES_TEST_URL")
def test_postgresql_round_trip_backup_restore_verify(tmp_path, monkeypatch):
    try:
        br.find_tool("pg_dump"), br.find_tool("pg_restore")
    except br.BackupError:
        pytest.skip("pg_dump/pg_restore not installed")
    import psycopg
    parsed = urlparse(PG_URL.replace("postgresql+psycopg://", "postgresql://", 1))
    monkeypatch.setenv("PGPASSWORD", parsed.password or "")
    base = f"postgresql://{parsed.username}@{parsed.hostname}:{parsed.port or 5432}"
    src_name, dst_name = f"asaa_bk_src_{uuid.uuid4().hex[:8]}", f"asaa_bk_dst_{uuid.uuid4().hex[:8]}"
    admin = psycopg.connect(host=parsed.hostname, port=parsed.port or 5432, user=parsed.username, password=parsed.password,
                            dbname=parsed.path.lstrip("/"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{src_name}"')
        admin.execute(f'CREATE DATABASE "{dst_name}"')
        pw = f"{parsed.username}:{parsed.password}"
        migrate(f"postgresql+psycopg://{pw}@{parsed.hostname}:{parsed.port or 5432}/{src_name}")
        with psycopg.connect(host=parsed.hostname, port=parsed.port or 5432, user=parsed.username, password=parsed.password, dbname=src_name) as c:
            for i in range(40):
                c.execute("INSERT INTO ap_suppliers (id, organization_id, legal_name, normalized_legal_name, status, version, created_at, updated_at, created_by, updated_by) "
                          "VALUES (%s,'org-a',%s,%s,'Draft',1,now(),now(),'t','t')", (str(uuid.uuid4()), f"S{i}", f"s{i}"))
        artifact = br.backup(f"{base}/{src_name}", tmp_path)
        assert br.verify_backup(artifact)["tables"]["ap_suppliers"] == 40
        result = br.restore(artifact, f"{base}/{dst_name}", verify=True)
        assert result["verified"] and result["rows"] >= 40
        data = bytearray(artifact.read_bytes())
        data[len(data) // 2] ^= 0xFF
        artifact.write_bytes(bytes(data))
        with pytest.raises(br.BackupError):
            br.verify_backup(artifact)
    finally:
        for name in (src_name, dst_name):
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


# ---------------- AES-256-GCM, retention, scheduling, staleness ----------------
import json  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402


def test_aes_gcm_multi_frame_round_trip_and_tamper_truncation_reorder_detection(tmp_path):
    key_file = tmp_path / "k"
    key_file.write_text(br.generate_key())
    plain = tmp_path / "big.bin"
    plain.write_bytes(os.urandom(br.FRAME * 3 + 123))
    enc = br.encrypt_file(plain, str(key_file))
    assert enc.read_bytes().startswith(br.MAGIC)
    out = br.decrypt_to_temp(enc, str(key_file))
    assert out.stat().st_size == br.FRAME * 3 + 123
    out.unlink()
    raw = enc.read_bytes()
    frame = 4 + 12 + br.FRAME + 16
    first, second = raw[len(br.MAGIC):len(br.MAGIC) + frame], raw[len(br.MAGIC) + frame:len(br.MAGIC) + 2 * frame]
    cases = {
        "bit flip": raw[:200] + bytes([raw[200] ^ 1]) + raw[201:],
        "truncated at frame boundary": raw[:len(br.MAGIC) + 2 * frame],
        "truncated mid frame": raw[:-50],
        "reordered frames": br.MAGIC + second + first + raw[len(br.MAGIC) + 2 * frame:],
        "bad header": b"XXXXXXXX" + raw[8:],
    }
    for name, blob in cases.items():
        bad = tmp_path / "bad.enc"
        bad.write_bytes(blob)
        with pytest.raises(br.BackupError):
            br.decrypt_to_temp(bad, str(key_file))


def test_key_validation_and_env_key_round_trip(populated_sqlite, tmp_path, monkeypatch):
    url, _ = populated_sqlite
    with pytest.raises(br.BackupError, match="not found"):
        br.backup(url, tmp_path / "a", encrypt_key_file="env:ASAA_NO_SUCH_KEY")
    monkeypatch.setenv("ASAA_SHORT_KEY", "c2hvcnQ")
    with pytest.raises(br.BackupError, match="32 bytes"):
        br.backup(url, tmp_path / "a", encrypt_key_file="env:ASAA_SHORT_KEY")
    monkeypatch.setenv("ASAA_BACKUP_KEY", br.generate_key())
    artifact = br.backup(url, tmp_path / "b", encrypt_key_file="env:ASAA_BACKUP_KEY")
    assert artifact.suffix == ".enc"
    target = tmp_path / "r.db"
    assert br.restore(artifact, f"sqlite:///{target.as_posix()}", "env:ASAA_BACKUP_KEY")["verified"] is True
    monkeypatch.setenv("ASAA_BACKUP_KEY", br.generate_key())  # a different key must not decrypt
    with pytest.raises(br.BackupError):
        br.verify_backup(artifact, "env:ASAA_BACKUP_KEY")


def fake_backup(out: Path, when: datetime):
    name = f"asaa-{when.strftime('%Y%m%dT%H%M%SZ')}.sqlite"
    (out / name).write_bytes(b"x")
    (out / (name + ".manifest.json")).write_text(json.dumps({"artifact": name, "created_at": when.isoformat(), "sha256": "x", "size_bytes": 1}))
    return name


def test_retention_keeps_daily_weekly_monthly_and_always_the_newest(tmp_path):
    base = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)
    names = [fake_backup(tmp_path, base - timedelta(days=d, hours=h)) for d in range(0, 120) for h in (0, 5)]
    result = br.rotate(tmp_path, keep_daily=3, keep_weekly=2, keep_monthly=3)
    kept = set(result["kept"])
    assert names[0] in kept  # newest
    newest_days = {n[5:13] for n in kept}
    assert {"20261113", "20261112", "20261111"} <= newest_days
    assert len(kept) <= 3 + 2 + 3 and len(kept) >= 5
    assert not (tmp_path / names[2]).exists()  # older same-day duplicate pruned
    assert not (tmp_path / (names[2] + ".manifest.json")).exists()
    assert (tmp_path / names[0]).exists()
    # idempotent
    assert br.rotate(tmp_path, 3, 2, 3)["deleted"] == []


def test_scheduled_run_records_status_and_staleness_check_for_monitoring(populated_sqlite, tmp_path, monkeypatch, capsys):
    url, _ = populated_sqlite
    monkeypatch.setenv("ASAA_BACKUP_KEY", br.generate_key())
    out = tmp_path / "sched"
    assert br.check_staleness(out, 26)["ok"] is False  # nothing recorded yet
    assert br.main(["check-staleness", "--out", str(out)]) == 2
    status = br.scheduled(url, out, "env:ASAA_BACKUP_KEY")
    assert status["last_artifact"].endswith(".enc") and status["last_error"] is None
    fresh = br.check_staleness(out, 26)
    assert fresh["ok"] is True
    assert br.main(["check-staleness", "--out", str(out), "--max-age-hours", "26"]) == 0
    stale = br.check_staleness(out, 26, now=datetime.now(timezone.utc) + timedelta(hours=40))
    assert stale["ok"] is False and "old" in stale["reason"]
    # a failing run (missing database) is recorded and flips the check even though an older backup exists
    with pytest.raises(br.BackupError):
        br.scheduled(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}", out, "env:ASAA_BACKUP_KEY")
    failed = br.check_staleness(out, 26)
    assert failed["ok"] is False and "failed" in failed["reason"]
    # deleting the artifact is detected too
    (out / "backup-status.json").write_text(json.dumps({**json.loads((out / "backup-status.json").read_text()), "last_failure_at": None}))
    for f in out.glob("*.enc"):
        f.unlink()
    assert "missing" in br.check_staleness(out, 26)["reason"]


def test_failed_scheduled_run_never_prunes_existing_backups(populated_sqlite, tmp_path):
    url, _ = populated_sqlite
    out = tmp_path / "keep"
    br.scheduled(url, out, None)
    before = sorted(p.name for p in out.glob("asaa-*"))
    with pytest.raises(br.BackupError):
        br.scheduled(f"sqlite:///{(tmp_path / 'gone.db').as_posix()}", out, None, keep=(1, 1, 1))
    assert sorted(p.name for p in out.glob("asaa-*")) == before


def test_keygen_cli_outputs_a_valid_key(capsys):
    assert br.main(["keygen"]) == 0
    key = capsys.readouterr().out.strip()
    import base64
    assert len(base64.urlsafe_b64decode(key)) == 32
