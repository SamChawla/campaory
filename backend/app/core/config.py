from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EXAMPLE_SECRET = "change-me-to-64-random-hex-chars"  # noqa: S105 (placeholder, rejected in prod)
DEFAULT_STATIC_DIR = str(Path(__file__).resolve().parents[2] / "static")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    base_url: str = "http://localhost:8000"
    session_secret: str = EXAMPLE_SECRET
    database_url: str = "sqlite:///./dev.db"
    static_dir: str = DEFAULT_STATIC_DIR

    llm_provider: Literal["mock", "euri"] = "mock"
    llm_fallback_to_mock: bool = False
    llm_timeout_seconds: float = 25
    euri_api_key: str = ""
    euri_model: str = ""
    euri_base_url: str = "https://api.euron.one/api/v1/euri"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    rate_guest_per_hour: int = 10
    rate_guest_per_day: int = 30
    rate_user_per_hour: int = 40
    rate_ip_per_minute: int = 120
    llm_daily_cap: int = 500
    free_plan_max_campaigns: int = 1

    sentry_dsn: str = ""

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def _production_needs_real_secret(self) -> "Settings":
        if self.app_env == "production" and self.session_secret in ("", EXAMPLE_SECRET):
            raise ValueError("SESSION_SECRET must be set in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
