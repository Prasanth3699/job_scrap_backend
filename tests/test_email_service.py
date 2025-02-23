import sys
import os
from pathlib import Path
import pytest
from datetime import date
from app.services.email_service import send_email_report
from app.models.job import Job
from app.db.session import get_db
from app.services.settings_service import SettingsService

pytestmark = pytest.mark.asyncio

# Sample job data for testing
SAMPLE_JOBS = [
    Job(
        job_title="Senior Python Developer",
        company_name="Tech Corp",
        job_type="Full-time",
        salary="$120,000 - $150,000",
        experience="5+ years",
        location="New York, NY",
        apply_link="https://example.com/job1",
        detail_url="https://example.com/job1-details",
        description="Looking for an experienced Python developer...",
    ),
    Job(
        job_title="Frontend Developer",
        company_name="Web Solutions",
        job_type="Remote",
        salary="$90,000 - $110,000",
        experience="3+ years",
        location="Remote",
        apply_link="https://example.com/job2",
        detail_url="https://example.com/job2-details",
        description="Seeking a talented frontend developer...",
    ),
]

# Real email settings for testing
TEST_EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_sender": "nandhatamil29@gmail.com",  # Replace with your Gmail
    "email_password": "mcmmfqwguqbszysq",  # Replace with your app password
    "email_receiver": "prasanthranger09@gmail.com",  # Replace with receiver's email
}


def create_linkedin_format(jobs):
    """Create LinkedIn post format from jobs."""
    text = "🎯 Latest Job Opportunities!\n\n"

    for job in jobs:
        text += f"🏢 {job.job_title}\n"
        if job.company_name:
            text += f"🏪 {job.company_name}\n"
        if job.job_type and job.job_type != "N/A":
            text += f"💼 {job.job_type}\n"
        if job.salary and job.salary != "N/A":
            text += f"💰 {job.salary}\n"
        if job.experience and job.experience != "N/A":
            text += f"📚 Experience: {job.experience}\n"
        text += f"🔗 Apply here: {job.apply_link}\n\n"

    text += "#jobs #careers #opportunities #hiring"
    return text


@pytest.fixture(autouse=True)
def setup_test_settings(db):
    """Setup test settings in the database"""
    settings = SettingsService.get_settings(db)
    settings.email_config = TEST_EMAIL_CONFIG
    db.commit()
    return settings


async def test_email_sending_with_jobs(db):
    """Test sending email with job data"""
    linkedin_format = create_linkedin_format(SAMPLE_JOBS)

    result = await send_email_report(
        "Test Job Report - Sample Jobs",
        "email/job_report.html",
        {
            "jobs": SAMPLE_JOBS,
            "date": date.today(),
            "linkedin_format": linkedin_format,
        },
        db,
    )

    assert result is True


async def test_email_sending_no_jobs(db):
    """Test sending email with no jobs"""
    result = await send_email_report(
        "Test Job Report - No Jobs",
        "email/job_report.html",
        {
            "jobs": [],
            "date": date.today(),
            "linkedin_format": "",
        },
        db,
    )

    assert result is True


def test_linkedin_format_creation():
    """Test LinkedIn format creation"""
    linkedin_format = create_linkedin_format(SAMPLE_JOBS)

    assert "Latest Job Opportunities!" in linkedin_format
    assert "Senior Python Developer" in linkedin_format
    assert "Frontend Developer" in linkedin_format
    assert "#jobs #careers #opportunities" in linkedin_format
