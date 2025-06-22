# tasks.py
from celery import shared_task
from celery.exceptions import Ignore
from loguru import logger
from .services.scraper_service import scrape_and_process_jobs
from .db.session import SessionLocal
from .utils.task_lock import RedisLock


@shared_task(bind=True)
def run_scraping_job(self, source_id: int = None):
    """Celery task to run the scraping job"""
    lock_name = f"scraping_task:{source_id if source_id else 'all'}"

    try:
        # Check if task is already running
        if RedisLock.is_locked(lock_name):
            logger.warning(f"Task {lock_name} is already running")
            raise Ignore()

        # Acquire lock
        if not RedisLock.acquire_lock(lock_name):
            logger.warning(f"Failed to acquire lock for {lock_name}")
            raise Ignore()

        logger.info(f"Starting scraping task for source_id: {source_id}")
        db = SessionLocal()
        result = scrape_and_process_jobs(source_id=source_id)
        db.close()
        return result

    except Ignore:
        raise

    except Exception as e:
        logger.error(f"Scraping task failed: {str(e)}")
        raise

    finally:
        # Release lock in finally block to ensure it's always released
        RedisLock.release_lock(lock_name)
