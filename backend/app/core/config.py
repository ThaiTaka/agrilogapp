"""Application configuration, loaded from environment / `.env`.

A single `settings` instance is imported everywhere. It is cached so the `.env`
file is parsed exactly once per process.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ───────────────────────────────────────────────────────────────
    APP_NAME: str = "AgriLog API"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # ─── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agrilog"
    TEST_DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/agrilog_test"
    )
    SQL_ECHO: bool = False

    # ─── JWT ───────────────────────────────────────────────────────────────
    JWT_SECRET: str = "insecure-development-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7   # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    # ─── CORS ──────────────────────────────────────────────────────────────
    # Kept as a raw string: pydantic-settings tries to JSON-decode `list[str]`
    # fields, which rejects the far more ergonomic comma-separated form.
    CORS_ORIGINS: str = "http://localhost:8081"

    # ─── Sync engine ───────────────────────────────────────────────────────
    SYNC_CLOCK_SKEW_TOLERANCE_MS: int = 300_000
    SYNC_MAX_BATCH_RECORDS: int = 5_000

    # The pull endpoint rewinds its cursor by this much before querying.
    #
    # A row's server_updated_at is stamped when it is written, but the row only
    # becomes visible to other transactions when it COMMITS. A transaction that
    # writes at T5 and commits at T8 is invisible to a pull that runs at T6 and
    # stores cursor=T6 -- and would then be skipped forever. Rewinding the
    # cursor by a margin larger than the longest write transaction closes that
    # window. Re-delivering a row is harmless: the client applies changes as an
    # upsert keyed on a client-generated ID, so a duplicate pull is a no-op.
    # The design trades a few redundant rows for the impossibility of a lost one.
    SYNC_CURSOR_SAFETY_MARGIN_MS: int = 2_000

    # ─── Locale ────────────────────────────────────────────────────────────
    # Vietnam is UTC+7 year-round (no DST since 1975). This constant is what
    # makes the generated `*_day_local` columns immutable and therefore
    # indexable. See Data_Requirements_Database.md section 7.2.
    APP_TZ_OFFSET_MS: int = Field(default=7 * 60 * 60 * 1000, frozen=True)

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL")
    @classmethod
    def _require_psycopg_driver(cls, v: str) -> str:
        """Fail fast on the single most common local-setup mistake.

        A bare `postgresql://` URL makes SQLAlchemy reach for psycopg2, which
        is not installed — producing a ModuleNotFoundError far from its cause.
        """
        if v.startswith("postgresql://"):
            raise ValueError(
                "Use the psycopg 3 scheme 'postgresql+psycopg://', not 'postgresql://'. "
                f"Got: {v.split('@')[-1]}"
            )
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
