from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables. No secrets in the repo."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # App
    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "Remarka API"
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    API_URL: str = "http://localhost:8000/api/v1"
    SECRET_KEY: str = "dev-insecure-secret-change-me"
    ACCESS_TOKEN_TTL_HOURS: int = 720
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:4173"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://remarka:remarka@localhost:5432/remarka"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_INIT_DATA_MAX_AGE_SECONDS: int = 86400

    # Books
    GOOGLE_BOOKS_API_KEY: str = ""
    GOOGLE_BOOKS_BASE_URL: str = "https://www.googleapis.com/books/v1"
    OPEN_LIBRARY_BASE_URL: str = "https://openlibrary.org"
    BOOK_SEARCH_MIN_RESULTS: int = 5

    # AI
    AI_PROVIDER: Literal["openai", "fake"] = "openai"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    AI_TOP_K: int = 8
    AI_MIN_RELEVANCE: float = 0.15
    AI_MAX_QUESTION_LENGTH: int = 1000

    # Limits
    FREE_AI_REQUESTS_PER_MONTH: int = 10
    PREMIUM_AI_REQUESTS_PER_MONTH: int = 500

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_DIR: str = "./data/uploads"
    STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000/uploads"
    UPLOAD_MAX_BYTES: int = 5 * 1024 * 1024

    # Billing
    TELEGRAM_PREMIUM_PRICE_STARS: int = 250
    PREMIUM_PERIOD_DAYS: int = 30
    ENABLE_TELEGRAM_STARS: bool = True
    ENABLE_YOOKASSA: bool = False
    ENABLE_PLATEGA: bool = False
    ENABLE_CRYPTOBOT: bool = False

    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    PLATEGA_API_KEY: str = ""
    PLATEGA_MERCHANT_ID: str = ""
    CRYPTOBOT_TOKEN: str = ""

    # Rate limiting
    RATE_LIMIT_BACKEND: Literal["memory", "redis"] = "memory"
    REDIS_URL: str = ""
    RATE_LIMIT_ENABLED: bool = True

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Accept plain postgres:// URLs from hosting providers and make them async.
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.APP_ENV in ("development", "test")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
