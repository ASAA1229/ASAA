from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASAA_AP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./asaa_ap.db"
    jwt_public_key: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_algorithm: str = "RS256"
    supplier_status_transitions_json: str = '{"Draft":["Pending Verification","Archived"],"Pending Verification":["Active","On Hold","Archived"],"Active":["On Hold","Suspended","Archived"],"On Hold":["Active","Suspended","Archived"],"Suspended":["Active","On Hold","Archived"],"Archived":[]}'
    app_name: str = "ASAA Finance API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
