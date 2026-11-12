from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASAA_AP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./asaa_ap.db"
    jwt_public_key: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_algorithm: str = "RS256"
    app_name: str = "ASAA AP API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
