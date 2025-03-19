# debug_scraper.py
import sys
import traceback
from app.db.session import SessionLocal
from app.services.scraper_service import scrape_and_process_jobs
from app.utils.redis_lock import RedisLock


def debug_scraper():
    db = SessionLocal()
    lock_name = "debug_scraping_task"

    try:
        # Check and release any existing locks
        if RedisLock.is_locked(lock_name):
            print(f"Releasing existing lock: {lock_name}")
            RedisLock.release_lock(lock_name)

        # Attempt to acquire lock
        if not RedisLock.acquire_lock(lock_name):
            print(f"Could not acquire lock: {lock_name}")
            return

        print("Starting scraper debugging...")
        result = scrape_and_process_jobs()
        print("Scraping completed successfully:")
        print(result)

    except Exception as e:
        print("Scraping failed:")
        print(f"Error: {e}")
        print("Traceback:")
        traceback.print_exc()

    finally:
        # Always release the lock
        RedisLock.release_lock(lock_name)

        # Close database session
        db.close()


if __name__ == "__main__":
    debug_scraper()
