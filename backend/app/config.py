"""Application configuration.

All tunables come from the environment (or a local .env). The most important
one is DATABASE_URL: switching that single value moves the whole app between
PostgreSQL and Db2 with no code change (PRD section 11, portability invariant).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"", "dev-only-change-me", "change-me", "secret", "changeme"}


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
    access_token_expire_minutes: int = 120

    # --- CORS ---
    # Kept as a comma-separated string so pydantic-settings does not try to
    # JSON-decode it as a "complex" field; use `.cors_origin_list` for the list.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Proxies ---
    # Only honor a client-supplied X-Forwarded-For header when the app runs
    # behind a trusted reverse proxy; otherwise use the socket peer address so
    # the header cannot be spoofed to bypass IP-based rate limiting.
    trust_forwarded_for: bool = False

    # --- Matching / lifecycle defaults (seeded into system_config) ---
    hold_ttl_minutes: int = 10
    match_score_threshold: int = 50
    max_eta_minutes: int = 180

    # --- Seed / bootstrap credentials ---
    # Never hardcode real credentials here: these are read from the environment
    # (a git-ignored backend/.env) and default to empty so nothing ships in the
    # repo. `seed_password` is used for the synthetic demo accounts; the
    # bootstrap admin is (re)created at startup from ADMIN_USERNAME /
    # ADMIN_PASSWORD so a temp login always exists without the credential ever
    # living in code or reaching the browser.
    seed_password: str = ""
    admin_username: str = ""
    admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _require_strong_secret_in_production(self) -> Settings:
        """Fail closed: never boot production with a weak/default signing secret."""
        insecure = (
            self.jwt_secret_key in _INSECURE_SECRETS or len(self.jwt_secret_key) < 32
        )
        if insecure and self.is_production:
            raise ValueError(
                "JWT_SECRET_KEY must be a strong random value of at least 32 "
                "characters when ENVIRONMENT=production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
