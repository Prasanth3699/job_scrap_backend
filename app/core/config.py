from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Job Scraper"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database Settings
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Email Settings
    EMAIL_SENDER: str
    EMAIL_PASSWORD: str
    EMAIL_RECEIVER: str
    SMTP_SERVER: str
    SMTP_PORT: int

    # Scheduler Settings
    SCRAPE_SCHEDULE_HOUR: int = 9
    SCRAPE_SCHEDULE_MINUTE: int = 0

    # Selenium Settings
    SELENIUM_TIMEOUT: int = 30
    SELENIUM_HEADLESS: bool = True

    SECRET_KEY: str = (
        "bcd2ea681c63e1e6a4362f267c18ceffc318f95111c52d420c11516bfa8dfa6a2e51c863d6521787f336b799e209f8eb648a66a3f1d4abee2e97235b32592d6b46b312bb046ab8a5a8d540dfd0f6b2a8936c64bb911e91bf54073e54abfceafe55b19fcf62c789f1704734253367e24074f7e8cb2182b228998951536a972b70bd7d30032600941206b1d21dd3e44c289a015037c5a480cf7b49390bab7cbe3e38d211aeaf9444ef4ac80b0df7f69dbc5d3e3ec1da30bdc5e54ae1585f3b683c58417b5463c3ab9d41882ca7737b58fae0c199c70a4eecfe485a0ad9f33cf798b56a1733c6c25a447541af5edda5dc6a713f7196813c992191837ced8da9476c"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # New Email Settings
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str

    # frontend url
    FRONTEND_URL: str

    # New Notification Settings
    SLACK_WEBHOOK_URL: str | None = None
    DISCORD_WEBHOOK_URL: str | None = None

    allowed_origins: List[AnyHttpUrl] = []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
