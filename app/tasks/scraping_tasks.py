from app.core.celery_app import celery_app
from celery.utils.log import get_task_logger
from app.services.scraper_service import scrape_and_process_jobs

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.scraper_tasks.scrape_jobs_task",
    bind=True,
    max_retries=3,
    queue="scraper",
)
def scrape_jobs_task(self):
    try:
        logger.info("Starting job scraping task")
        # scraper = JobScraper()
        # result = scraper.scrape_jobs()
        result = scrape_and_process_jobs()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        raise self.retry(exc=e)
