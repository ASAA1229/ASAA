from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASAA_AP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./asaa_ap.db"
    jwt_public_key: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_algorithm: str = "RS256"
    jwt_jwks_url: str | None = None
    required_acr: str | None = None
    required_amr: str | None = None
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    supplier_status_transitions_json: str = '{"Draft":["Pending Verification","Archived"],"Pending Verification":["Active","On Hold","Archived"],"Active":["On Hold","Suspended","Archived"],"On Hold":["Active","Suspended","Archived"],"Suspended":["Active","On Hold","Archived"],"Archived":[]}'
    cors_origins: list[str] = ["http://localhost:5000", "http://127.0.0.1:5000"]
    app_name: str = "ASAA Finance API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
