from sqlalchemy.orm import Session
from ..models.settings import Settings
from ..core.logger import logger
from typing import Dict, Any


class SettingsService:
    @staticmethod
    def get_settings(db: Session) -> Settings:
        """Get settings from database or create with defaults if not exists"""
        settings = db.query(Settings).filter(Settings.is_active == True).first()

        if not settings:
            # Create default settings
            default_config = Settings.get_default_config()
            settings = Settings(
                app_name=default_config["app_name"],
                email_config=default_config["email_config"],
                scheduler_config=default_config["scheduler_config"],
                selenium_config=default_config["selenium_config"],
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
            logger.info("Created default settings in database")

        return settings

    @staticmethod
    def update_settings(db: Session, settings_data: Dict[str, Any]) -> Settings:
        """Update settings in database"""
        settings = SettingsService.get_settings(db)

        if "email_config" in settings_data:
            settings.email_config = settings_data["email_config"]
        if "scheduler_config" in settings_data:
            settings.scheduler_config = settings_data["scheduler_config"]
        if "selenium_config" in settings_data:
            settings.selenium_config = settings_data["selenium_config"]
        if "app_name" in settings_data:
            settings.app_name = settings_data["app_name"]

        db.commit()
        db.refresh(settings)
        logger.info("Updated settings in database")
        return settings

    @staticmethod
    def get_email_config(db: Session) -> Dict[str, Any]:
        """Get email configuration"""
        settings = SettingsService.get_settings(db)
        return settings.email_config

    @staticmethod
    def get_scheduler_config(db: Session) -> Dict[str, Any]:
        """Get scheduler configuration"""
        settings = SettingsService.get_settings(db)
        return settings.scheduler_config

    @staticmethod
    def get_selenium_config(db: Session) -> Dict[str, Any]:
        """Get selenium configuration"""
        settings = SettingsService.get_settings(db)
        return settings.selenium_config
