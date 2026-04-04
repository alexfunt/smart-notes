from datetime import timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Smart Notes API"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 55432
    POSTGRES_DB: str = "smart_notes"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/smart_notes"

    TELEGRAM_BOT_TOKEN: str = ""
    BACKEND_API_URL: str = "http://127.0.0.1:8000"

    #: Minutes until first/next reminder (default 1440 = 24h). Use 1 for local testing.
    TASK_REMINDER_INTERVAL_MINUTES: int = 1

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_HINT_MIN_ENGAGEMENT_SCORE: float = 0.55

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def task_reminder_delta(self) -> timedelta:
        return timedelta(minutes=self.TASK_REMINDER_INTERVAL_MINUTES)


settings = Settings()