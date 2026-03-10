from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_DIR = Path(__file__).resolve().parent
_DEFAULT_DB = f"sqlite+aiosqlite:///{_PROJECT_DIR / 'data' / 'kurs_uz.db'}"


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = _DEFAULT_DB

    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"
    COLLECTION_INTERVAL_MINUTES: int = 15
    RETENTION_DAYS: int = 90

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]
