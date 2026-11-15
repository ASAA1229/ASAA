from functools import lru_cache
from typing import Literal

from pydantic import model_validator

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASAA_AP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./asaa_ap.db"
    environment: Literal["development", "test", "staging", "production"] = "development"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    jwt_public_key: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_algorithm: str = "RS256"
    jwt_jwks_url: str | None = None
    jwks_refresh_cooldown_seconds: float = Field(default=10, ge=0, le=300)
    required_acr: str | None = None
    required_amr: str | None = None
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    supplier_status_transitions_json: str = '{"Draft":["Pending Verification","Archived"],"Pending Verification":["Active","On Hold","Archived"],"Active":["On Hold","Suspended","Archived"],"On Hold":["Active","Suspended","Archived"],"Suspended":["Active","On Hold","Archived"],"Archived":[]}'
    cors_origins: list[str] = ["http://localhost:5000", "http://127.0.0.1:5000"]
    app_name: str = "ASAA Finance API"
    log_level: str = "INFO"
    # Identity lifecycle adapter name. "none" = not configured. "memory" is a mock for dev/test only.
    identity_provider: str = "none"
    scim_base_url: str | None = None
    scim_bearer_token: str | None = None
    scim_group_prefix: str = "asaa:"
    # Directory written by scripts/backup_restore.py scheduled (read-only status view). Unset = backup status not configured.
    backup_dir: str | None = None
    backup_max_age_hours: float = 26
    # Notification delivery adapter name. "none" = not configured; "memory" is a mock for dev/test only.
    notification_provider: str = "none"
    # When set, GET /metrics requires "Authorization: Bearer <token>". In production /metrics is disabled unless set.
    metrics_token: str | None = None


    @model_validator(mode="after")
    def production_database_must_be_postgresql(self):
        if self.environment == "production" and not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("Production requires a PostgreSQL database URL")
        if self.environment == "production" and self.identity_provider == "memory":
            raise ValueError("The in-memory identity provider must not be used in production")
        if self.environment == "production" and self.notification_provider == "memory":
            raise ValueError("The in-memory notification provider must not be used in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
