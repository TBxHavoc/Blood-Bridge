"""Application configuration.

All tunables come from the environment (or a local .env). The most important
one is DATABASE_URL: switching that single value moves the whole app between
PostgreSQL and Db2 with no code change (PRD section 11, portability invariant).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "Blood Bridge API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    # --- Database (the portability switch) ---
    database_url: str = (
        "postgresql+psycopg://bloodbridge:bloodbridge@localhost:5432/bloodbridge"
    )
    db_echo: bool = False

    # --- Auth ---
    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # --- CORS ---
    # Kept as a comma-separated string so pydantic-settings does not try to
    # JSON-decode it as a "complex" field; use `.cors_origin_list` for the list.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Matching / lifecycle defaults (seeded into system_config) ---
    hold_ttl_minutes: int = 10
    match_score_threshold: int = 50
    max_eta_minutes: int = 180

    # --- Seed ---
    seed_password: str = "Password123!"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
