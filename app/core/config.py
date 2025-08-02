from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Job Scraper"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    INTER_SERVICE_SECRET: str

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

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for development
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

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

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Redis Configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: Optional[str]
    REDIS_URL: str

    # RabbitMQ Configuration
    RABBITMQ_URL: str
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Admin Configuration
    ADMIN_SECRET_KEY: str = "admin-super-secret-key-change-in-production"

    # Service Authentication
    SERVICE_SECRET_KEY: str = "service-to-service-communication-secret"
    JWT_SECRET_KEY: str = "jwt-signing-secret-key-change-in-production"

    allowed_origins: List[AnyHttpUrl] = []

    # Websocket Settings
    WS_SECRET_KEY: str = "1234567890"
    APP2_URL: str = "http://localhost:8001"

    # Internal Service URLs
    ML_SERVICE_URL: str = "http://ml-service:8001"
    LLM_SERVICE_URL: str = "http://llm-service:8002"
    ANALYTICS_SERVICE_URL: str = "http://analytics-service:8003"

    # Data Retention Configuration (in days)
    DATA_RETENTION_JOBS: int = 90
    DATA_RETENTION_LOGS: int = 30
    DATA_RETENTION_METRICS: int = 7
    DATA_RETENTION_CACHE: int = 1

    # Monitoring Configuration
    ENABLE_METRICS: bool = True
    METRICS_EXPORT_INTERVAL: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
