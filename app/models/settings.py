from sqlalchemy import Column, DateTime, Integer, String, JSON, Boolean
from sqlalchemy.sql import func
from ..db.base import Base


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    app_name = Column(String(255), default="Job Scraper")
    email_config = Column(JSON, nullable=False)
    scheduler_config = Column(JSON, nullable=False)
    selenium_config = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Default configurations
    @staticmethod
    def get_default_config():
        return {
            "app_name": "Job Scraper",
            "email_config": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "email_sender": "",
                "email_password": "",
                "email_receiver": "",
            },
            "scheduler_config": {
                "scrape_schedule_hour": 9,
                "scrape_schedule_minute": 0,
                "enabled": True,
            },
            "selenium_config": {"timeout": 30, "headless": True},
        }
