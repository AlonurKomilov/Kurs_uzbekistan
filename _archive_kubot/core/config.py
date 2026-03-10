"""Centralized configuration using Pydantic settings validation."""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required
    DATABASE_URL: str = Field(..., description="PostgreSQL async connection string")
    BOT_TOKEN: str = Field(..., description="Telegram bot token from @BotFather")

    # Optional with defaults
    TWA_BASE_URL: str = Field("http://localhost:3000", description="Telegram Web App base URL")
    SENTRY_DSN: Optional[str] = Field(None, description="Sentry DSN for error tracking")
    ENVIRONMENT: str = Field("development", description="Deployment environment")
    SQL_DEBUG: bool = Field(False, description="Enable SQLAlchemy SQL echo logging")
    API_RATE_LIMIT: int = Field(60, description="API rate limit (requests per minute)")

    # Data retention
    BANK_RATES_RETENTION_DAYS: int = Field(90, description="Days to keep bank_rates rows")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    """Load and validate settings from environment. Raises ValidationError on missing required fields."""
    return Settings()  # type: ignore[call-arg]
