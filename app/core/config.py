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
    TASK_REMINDER_INTERVAL_MINUTES: int = 1440
    #: Множитель паузы при engagement→1 (чаще напоминать). Должен быть < MAX.
    TASK_REMINDER_ENGAGEMENT_MIN_GAP_MULTIPLIER: float = 0.35
    #: Множитель паузы при engagement→0 (реже напоминать).
    TASK_REMINDER_ENGAGEMENT_MAX_GAP_MULTIPLIER: float = 4.5
    #: Нижняя граница интервала в минутах после масштабирования.
    REMINDER_MIN_SPACING_MINUTES: int = 1
    #: Пауза (сек) между напоминаниями в один чат за один проход планировщика (не «пачкой»).
    REMINDER_STAGGER_SECONDS: float = 5.0
    #: Случайный сдвиг 0..N сек к next_check_at, чтобы задачи с одинаковой вовлечённостью не срабатывали синхронно.
    REMINDER_NEXT_CHECK_JITTER_MAX_SECONDS: int = 180

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    #: OpenAI-compatible chat completions base, без завершающего слэша (добавляется /chat/completions).
    #: DeepSeek: https://api.deepseek.com/v1
    LLM_CHAT_BASE_URL: str = "https://api.openai.com/v1"
    AI_HINT_MIN_ENGAGEMENT_SCORE: float = 0.55

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def task_reminder_delta(self) -> timedelta:
        return timedelta(minutes=self.TASK_REMINDER_INTERVAL_MINUTES)


settings = Settings()