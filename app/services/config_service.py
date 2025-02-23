from sqlalchemy.orm import Session
from ..models.settings import Settings
from ..core.config import get_settings
from ..schemas.settings import EmailConfig, CronConfig

env_settings = get_settings()


class ConfigService:
    @staticmethod
    def get_email_config(db: Session, user_id: int) -> EmailConfig:
        # Try to get user-specific settings
        settings = db.query(Settings).filter(Settings.user_id == user_id).first()

        if settings and settings.email_config:
            return EmailConfig(**settings.email_config)

        # Fallback to environment variables
        return EmailConfig(
            smtp_server=env_settings.DEFAULT_SMTP_SERVER,
            smtp_port=env_settings.DEFAULT_SMTP_PORT,
            sender_email=env_settings.DEFAULT_EMAIL_SENDER,
            receiver_email=env_settings.DEFAULT_EMAIL_RECEIVER,
        )

    @staticmethod
    def get_cron_config(db: Session, user_id: int) -> CronConfig:
        settings = db.query(Settings).filter(Settings.user_id == user_id).first()

        if settings and settings.cron_config:
            return CronConfig(**settings.cron_config)

        # Fallback to environment variables
        return CronConfig(
            schedule=f"{env_settings.DEFAULT_SCRAPE_SCHEDULE_MINUTE} {env_settings.DEFAULT_SCRAPE_SCHEDULE_HOUR} * * *",
            enabled=True,
        )
