# debug_scraper.py
import sys
import traceback
from loguru import logger


# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("scraper_debug.log", level="INFO")


def debug_scraper():
    print("Debug script started")  # Explicit print
    logger.info("Debug script started")  # Loguru log

    from app.db.session import SessionLocal
    from app.services.scraper_service import scrape_and_process_jobs
    from app.utils.redis_lock import RedisLock

    db = SessionLocal()
    lock_name = "debug_scraping_task"

    try:
        print("Checking and releasing existing locks")
        logger.info("Checking and releasing existing locks")

        if RedisLock.is_locked(lock_name):
            print(f"Releasing existing lock: {lock_name}")
            logger.info(f"Releasing existing lock: {lock_name}")
            RedisLock.release_lock(lock_name)

        print("Attempting to acquire lock")
        logger.info("Attempting to acquire lock")

        if not RedisLock.acquire_lock(lock_name):
            print(f"Could not acquire lock: {lock_name}")
            logger.error(f"Could not acquire lock: {lock_name}")
            return

        print("Starting scraper debugging...")
        logger.info("Starting scraper debugging...")

        result = scrape_and_process_jobs()

        print("Scraping completed successfully:")
        print(result)
        logger.success("Scraping completed successfully")
        logger.info(f"Result: {result}")

    except Exception as e:
        print("Scraping failed:")
        print(f"Error: {e}")
        print("Traceback:")
        traceback.print_exc()

        logger.error("Scraping failed")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())

    finally:
        RedisLock.release_lock(lock_name)
        db.close()


if __name__ == "__main__":
    debug_scraper()
