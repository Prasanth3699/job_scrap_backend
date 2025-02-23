import pytest
from app.services.settings_service import SettingsService


def test_get_settings(db):
    """Test getting settings"""
    settings = SettingsService.get_settings(db)
    assert settings is not None
    assert hasattr(settings, "email_config")
    assert hasattr(settings, "scheduler_config")


def test_update_email_settings(db):
    """Test updating email settings"""
    email_config = {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "email_sender": "test@example.com",
        "email_password": "test_password",
        "email_receiver": "receiver@example.com",
    }

    settings = SettingsService.update_settings(db, {"email_config": email_config})
    assert settings.email_config == email_config


def test_update_scheduler_settings(db):
    """Test updating scheduler settings"""
    scheduler_config = {
        "scrape_schedule_hour": 10,
        "scrape_schedule_minute": 30,
        "enabled": True,
    }

    settings = SettingsService.update_settings(
        db, {"scheduler_config": scheduler_config}
    )
    assert settings.scheduler_config == scheduler_config
