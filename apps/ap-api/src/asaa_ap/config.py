from decimal import Decimal
from functools import lru_cache
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, model_validator

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProducerMapping(BaseModel):
    """An ecosystem event producer: the token `azp` (client id) it authenticates with may only emit this source/project/type prefix."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    source: str
    project: Literal["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"]
    typePrefix: str

    @model_validator(mode="after")
    def prefix_belongs_to_the_source(self):
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", self.source):
            raise ValueError("producer source must look like a service id")
        if not self.typePrefix or not self.typePrefix.endswith(".") or not self.typePrefix.startswith(self.source + "."):
            raise ValueError("producer typePrefix must end with '.' and start with '<source>.'")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASAA_AP_", env_file=".env", extra="ignore", populate_by_name=True)

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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    app_name: str = "ASAA Finance API"
    log_level: str = "INFO"
    # Identity lifecycle adapter name. "none" = not configured. "memory" is a mock for dev/test only.
    identity_provider: str = "none"
    scim_base_url: str | None = None
    scim_bearer_token: str | None = None
    scim_group_prefix: str = "asaa:"
    # Keycloak adapter (ASAA_AP_IDENTITY_PROVIDER=keycloak). These use the ASAA_IDENTITY_KEYCLOAK_* names, not the ASAA_AP_ prefix.
    keycloak_url: str | None = Field(default=None, validation_alias="ASAA_IDENTITY_KEYCLOAK_URL")
    keycloak_realm: str = Field(default="asaa", validation_alias="ASAA_IDENTITY_KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="asaa-identity-sync", validation_alias="ASAA_IDENTITY_KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: SecretStr | None = Field(default=None, validation_alias="ASAA_IDENTITY_KEYCLOAK_CLIENT_SECRET")
    keycloak_base_group: str = Field(default="employees", validation_alias="ASAA_IDENTITY_KEYCLOAK_BASE_GROUP")
    # Roles the base group may map (JSON list; realm roles by name, client roles as "client/role"). Empty by default.
    keycloak_base_group_roles: list[str] = Field(default=[], validation_alias="ASAA_IDENTITY_KEYCLOAK_BASE_GROUP_ROLES")
    # Groups are never created by identity sync unless this is set; entitlement groups must exist (and carry no role mappings).
    keycloak_create_groups: bool = Field(default=False, validation_alias="ASAA_IDENTITY_KEYCLOAK_CREATE_GROUPS")
    # Directory written by scripts/backup_restore.py scheduled (read-only status view). Unset = backup status not configured.
    backup_dir: str | None = None
    # Owner policy values (D1.17). Unset = "policy not configured": backup freshness / restore time are reported but never judged against an assumed target.
    # backup_max_age_hours is the older name of the RPO check and is used only when backup_rpo_hours is unset.
    backup_max_age_hours: float | None = Field(default=None, gt=0, le=8760)
    backup_rpo_hours: float | None = Field(default=None, gt=0, le=8760)
    backup_rto_minutes: float | None = Field(default=None, gt=0, le=525600)
    # Notification delivery adapter name. "none" = not configured; "memory" is a mock for dev/test only.
    notification_provider: str = "none"
    # When set, GET /metrics requires "Authorization: Bearer <token>". In production /metrics is disabled unless set.
    metrics_token: str | None = None
    # Build commit SHA shown in the service manifest (set by the release pipeline); anything that is not 7-40 hex digits is ignored.
    build_commit: str | None = None
    # Ecosystem registry (contracts/ecosystem/v1/ecosystem-registry.json). Unset = auto-discover relative to the repository.
    ecosystem_registry_path: str | None = None
    # Sibling services are only contacted on loopback unless their host is listed here (JSON list of host names).
    ecosystem_allowed_hosts: list[str] = []
    # Allowlisted non-loopback hosts must use https unless listed here too (for example host.docker.internal on a developer machine).
    ecosystem_insecure_http_hosts: list[str] = []
    # Critical ecosystem events notify holders of integration:event:read / ops:ecosystem:read (approved role assignments) plus these
    # subjects (JSON list). Delivery goes through the notification outbox using the channel below.
    integration_critical_recipients: list[str] = []
    integration_critical_channel: str = "email"
    # Event producers keyed by token azp (client id), JSON, e.g.
    # {"jarvis-events":{"source":"jarvis","project":"JARVIS","typePrefix":"jarvis."}}. A token whose azp is not listed cannot write events.
    integration_producers: dict[str, ProducerMapping] = {}
    # Per-principal ingest rate limit (token bucket). The bucket lives in each API process: with N worker processes the effective
    # limit is N times these values, so size them per worker.
    integration_rate_per_minute: int = Field(default=120, ge=1, le=100000)
    integration_rate_burst: int = Field(default=30, ge=1, le=100000)
    # A critical alert for the same (source, type) is not repeated within this window.
    integration_critical_dedupe_minutes: int = Field(default=15, ge=0, le=1440)
    # Within the same window a source may raise alerts for at most this many distinct critical event types, so varying type names
    # cannot flood the recipients.
    integration_critical_source_max_streams: int = Field(default=3, ge=1, le=100)
    # Retention for ingested events, used by scripts/purge_integration_events.py. Default 180 days, approved by the owner (2026-11-18); keep it configurable.
    integration_event_retention_days: int = Field(default=180, ge=1, le=3650)
    # Event `time` must be within this many seconds of now (past or future).
    integration_clock_skew_seconds: int = Field(default=86400, ge=0, le=31536000)
    # Supplier-invoice match tolerance (absolute amount, invoice currency). Owner policy value (BLOCKED - OWNER). Unset = policy not configured:
    # matching is refused rather than assuming a tolerance. Set 0 explicitly for exact-match-only.
    # Swagger UI sign-in (/docs, never in production). Unset = bearer token paste only. The client is a public PKCE client: no secret exists here.
    docs_oidc_authorization_url: str | None = None
    docs_oidc_token_url: str | None = None
    docs_oidc_client_id: str | None = None
    ap_match_tolerance_amount: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000"))


    @model_validator(mode="after")
    def producers_must_be_unambiguous(self):
        clients = [c for c in self.integration_producers if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", c)]
        if clients:
            raise ValueError("ASAA_AP_INTEGRATION_PRODUCERS: invalid client id (azp)")
        for field in ("source", "typePrefix"):
            values = [getattr(m, field) for m in self.integration_producers.values()]
            if len(values) != len(set(values)):
                raise ValueError(f"ASAA_AP_INTEGRATION_PRODUCERS: two clients share the same {field}; each producer needs its own credential")
        return self

    @model_validator(mode="after")
    def cors_wildcard_only_in_development(self):
        if "*" in self.cors_origins and self.environment in {"staging", "production"}:
            raise ValueError("ASAA_AP_CORS_ORIGINS must list explicit origins in staging and production")
        return self

    @model_validator(mode="after")
    def docs_oidc_urls_must_be_https_off_loopback(self):
        from urllib.parse import urlparse
        for value in (self.docs_oidc_authorization_url, self.docs_oidc_token_url):
            if value:
                parsed = urlparse(value)
                if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
                    raise ValueError("ASAA_AP_DOCS_OIDC_*_URL must use https (plain http only on localhost / 127.0.0.1)")
        return self

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
