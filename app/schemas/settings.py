from pydantic import BaseModel, EmailStr


class EmailConfig(BaseModel):
    smtp_server: str
    smtp_port: int
    sender_email: EmailStr
    receiver_email: EmailStr


class CronConfig(BaseModel):
    schedule: str
    enabled: bool


class NotificationConfig(BaseModel):
    email_enabled: bool = True
    slack_enabled: bool = False
    slack_webhook: str | None = None


class SettingsUpdate(BaseModel):
    email_config: EmailConfig | None = None
    cron_config: CronConfig | None = None
    notification_config: NotificationConfig | None = None
