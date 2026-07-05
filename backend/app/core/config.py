"""
Centralized application configuration.

All environment-derived settings live here so that nothing in the codebase
reads `os.environ` directly. This keeps configuration testable (override via
`Settings(**overrides)`) and keeps secrets out of code.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "TalentFlow AI"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- CORS ---
    # NoDecode: pydantic-settings otherwise tries to JSON-decode any
    # List[str]-typed env var before our field_validator runs, which crashes
    # on a plain comma-separated string like "http://a.com,http://b.com".
    # NoDecode skips that and hands the raw string straight to the validator.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Postgres ---
    DATABASE_URL: str = "postgresql+psycopg2://talentflow:talentflow@localhost:5432/talentflow"
    DATABASE_ECHO: bool = False

    # --- Qdrant ---
    # Defaults to embedded/local mode (no server process required) so a fresh
    # clone runs with zero external infra. Point this at a real server URL
    # (e.g. http://localhost:6333) for staging/production.
    QDRANT_URL: str = "local:./storage/qdrant_data"
    QDRANT_API_KEY: str | None = None
    QDRANT_TIMEOUT: int = 30

    # Vector size must match the embedding model. text-embedding-3-small = 1536.
    EMBEDDING_DIM: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- LLM / OpenAI ---
    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"

    # --- Enkrypt AI (fairness / bias / grounding guardrails) ---
    ENKRYPT_API_KEY: str | None = None
    ENKRYPT_BASE_URL: AnyHttpUrl | None = None
    ENKRYPT_ENABLED: bool = True

    # --- Auth ---
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- Storage ---
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_DIR: str = "./storage/resumes"
    S3_BUCKET_NAME: str | None = None

    # --- Redis (cache / celery broker) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import and call this, don't instantiate Settings() directly."""
    return Settings()
