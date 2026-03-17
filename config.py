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

    ADMIN_IDS: str = ""
    HEALTH_PORT: int = 8080

    @property
    def admin_ids(self) -> set[int]:
        if not self.ADMIN_IDS.strip():
            return set()
        return {int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]
