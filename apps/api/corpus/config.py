from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from corpus.paths import ENV_FILE


class Settings(BaseSettings):
    # absolute, not ".env": the API runs from apps/api while .env lives at the
    # repo root, so a CWD-relative path finds nothing and every value below
    # silently falls back to its default.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://corpus:corpus@localhost:5432/corpus"
    redis_url: str = "redis://localhost:6379/0"

    kite_api_key: str = ""
    kite_api_secret: str = ""
    anthropic_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def _asyncpg_scheme(cls, v: str) -> str:
        """Managed providers (Railway, Heroku-style) hand out postgres:// or
        postgresql:// URLs; SQLAlchemy async needs the asyncpg driver spelled
        out. Normalise here so both the app and alembic get the same URL."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix) and "+asyncpg" not in v:
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
