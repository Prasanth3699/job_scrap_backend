from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ..core.logger import logger
from .settings_service import SettingsService
from .scraper_service import scrape_and_process_jobs
from ..db.session import SessionLocal

scheduler = AsyncIOScheduler()


def update_scheduler():
    """Update scheduler with database configuration"""
    db = SessionLocal()
    try:
        scheduler_config = SettingsService.get_scheduler_config(db)

        # Remove existing job if any
        if scheduler.get_job("daily_job_scrape"):
            scheduler.remove_job("daily_job_scrape")

        if scheduler_config["enabled"]:
            scheduler.add_job(
                scrape_and_process_jobs,
                trigger=CronTrigger(
                    hour=scheduler_config["scrape_schedule_hour"],
                    minute=scheduler_config["scrape_schedule_minute"],
                ),
                id="daily_job_scrape",
                name="Daily Job Scraping",
                replace_existing=True,
            )
            logger.info(
                f"Scheduled job scraping for {scheduler_config['scrape_schedule_hour']}:"
                f"{scheduler_config['scrape_schedule_minute']:02d}"
            )
    finally:
        db.close()


def init_scheduler():
    """Initialize the scheduler with database configuration"""
    try:
        scheduler.start()
        update_scheduler()
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")
        raise
