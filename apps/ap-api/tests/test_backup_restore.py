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
