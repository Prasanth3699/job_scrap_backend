from celery import shared_task
from loguru import logger
from app.services.scraper_service import scrape_and_process_jobs
from app.db.session import SessionLocal


@shared_task
def run_scraping_job():
    """Celery task to run the scraping job"""
    try:
        logger.info("Starting scraping task")
        db = SessionLocal()
        result = scrape_and_process_jobs()
        db.close()
        return result
    except Exception as e:
        logger.error(f"Scraping task failed: {str(e)}")
        raise
