import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = Field(default="Contract Insights API")
    APP_VERSION: str = Field(default="1.0.0")
    APP_DESCRIPTION: str = Field(
        default="Backend service for AI-powered contract analysis. Upload PDFs and retrieve extracted insights."
    )
    CORS_ALLOW_ORIGINS: str = Field(default="*")  # comma-separated

    # Security
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME")  # request from user in .env
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24)  # 24h

    # Database
    POSTGRES_URL: Optional[str] = Field(default=None)  # e.g., postgresql+asyncpg://user:pass@host:5432/db

    # File storage
    UPLOAD_DIR: str = Field(default="storage/uploads")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_BASE: Optional[str] = Field(default=None)
    OPENAI_MODEL: Optional[str] = Field(default=None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings (cached)."""
    # Settings class picks defaults; environment overrides via os.getenv handled by app config usage
    return Settings(
        APP_NAME=os.getenv("APP_NAME", Settings.model_fields["APP_NAME"].default),
        APP_VERSION=os.getenv("APP_VERSION", Settings.model_fields["APP_VERSION"].default),
        APP_DESCRIPTION=os.getenv("APP_DESCRIPTION", Settings.model_fields["APP_DESCRIPTION"].default),
        CORS_ALLOW_ORIGINS=os.getenv("CORS_ALLOW_ORIGINS", Settings.model_fields["CORS_ALLOW_ORIGINS"].default),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", Settings.model_fields["JWT_SECRET_KEY"].default),
        JWT_ALGORITHM=os.getenv("JWT_ALGORITHM", Settings.model_fields["JWT_ALGORITHM"].default),
        ACCESS_TOKEN_EXPIRE_MINUTES=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(Settings.model_fields["ACCESS_TOKEN_EXPIRE_MINUTES"].default))),
        POSTGRES_URL=os.getenv("POSTGRES_URL"),
        UPLOAD_DIR=os.getenv("UPLOAD_DIR", Settings.model_fields["UPLOAD_DIR"].default),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        OPENAI_API_BASE=os.getenv("OPENAI_API_BASE"),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL"),
    )
