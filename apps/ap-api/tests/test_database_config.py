import pytest
from pydantic import ValidationError

from asaa_ap.config import Settings


def test_local_frontend_cors_defaults_to_port_5173(monkeypatch):
    monkeypatch.delenv("ASAA_AP_CORS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_production_rejects_sqlite_database():
    with pytest.raises(ValidationError, match="Production requires a PostgreSQL database URL"):
        Settings(environment="production", database_url="sqlite:///./production.db")


def test_production_accepts_postgresql_database():
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://user:password@db.example.invalid/asaa",
    )
    assert settings.environment == "production"
