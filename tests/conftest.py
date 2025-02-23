import pytest
import os
from dotenv import load_dotenv
from pathlib import Path
from app.core.config import get_settings
from app.db.session import get_db
from app.services.settings_service import SettingsService


# Load test environment variables
test_env_path = Path(__file__).parent / ".env.test"
load_dotenv(test_env_path)


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def db():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_email_config():
    return {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "email_sender": os.getenv("TEST_EMAIL_SENDER"),
        "email_password": os.getenv("TEST_EMAIL_PASSWORD"),
        "email_receiver": os.getenv("TEST_EMAIL_RECEIVER"),
    }


@pytest.fixture(autouse=True)
def mock_settings_in_db(db):
    """Automatically insert mock settings into the database for all tests"""
    mock_settings = {
        "email_config": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "email_sender": "test@example.com",
            "email_password": "test_password",
            "email_receiver": "test@example.com",
        },
        "scheduler_config": {
            "scrape_schedule_hour": 9,
            "scrape_schedule_minute": 0,
            "enabled": True,
        },
        "selenium_config": {
            "timeout": 30,
            "headless": True,
        },
    }

    settings = SettingsService.get_settings(db)
    for key, value in mock_settings.items():
        setattr(settings, key, value)

    db.commit()
    return settings
