import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
from typing import List, Dict, Any, Optional
import pytz
import os
from functools import wraps
import traceback

from ..models.scraping_history import ScrapingHistory
from ..utils.linkedin_formatter import create_linkedin_format
from ..db.repositories.job_repository import JobRepository
from ..services.email_service import send_email_report
from ..db.session import SessionLocal
from ..core.config import get_settings
from ..core.constants import JOB_PAGE_URL, DEFAULT_WAIT
from ..utils.exceptions import ScraperException
from ..utils.decorators import retry_on_exception, log_execution_time
from sqlalchemy.orm import Session
from ..models.job import Job

# from ..core.celery_config import celery_app

settings = get_settings()

IST = pytz.timezone("Asia/Kolkata")

# Configuration
SCRAPER_CONFIG = {
    "max_retries": 3,
    "batch_size": 10,
    "page_load_timeout": 30,
    "element_timeout": 5,  # Reduced from 10 seconds
    "scroll_pause_time": 1,  # Reduced from 2 seconds
    "between_jobs_delay": 0.2,  # Reduced from 0.5 seconds
    "max_jobs": 20,
    "headless": True,
}


class ScraperException(Exception):
    """Custom exception for scraper-specific errors"""

    pass


class JobScraper:

    def __init__(self, db: Session):
        self.driver = None
        self.wait = None
        self.config = SCRAPER_CONFIG
        self.db = db

    def get_by_url(self, url: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.detail_url == url).first()

    async def store_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Store jobs in database"""
        stored_jobs = []
        try:
            for job_data in jobs:
                job = Job(
                    detail_url=job_data["detail_url"],
                    job_title=job_data["job_title"],
                    posting_date=datetime.datetime.strptime(
                        job_data["posting_date"], "%d %B %Y"
                    ).date(),
                    job_type=job_data["job_type"],
                    salary=job_data["salary"],
                    experience=job_data["experience"],
                    apply_link=job_data["apply_link"],
                    company_name=job_data["company_name"],
                    location=job_data["location"],
                    description=job_data["description"],
                )
                self.db.add(job)
                stored_jobs.append(job_data)

            self.db.commit()
            return stored_jobs
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error storing jobs: {str(e)}")
            raise

    def optimize_page_load(self):
        """Configure driver for faster page loading"""
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # Disable images
                "plugins": 2,  # Disable plugins
                "popups": 2,  # Disable popups
                "geolocation": 2,  # Disable geolocation
                "notifications": 2,  # Disable notifications
                "auto_select_certificate": 2,  # Disable SSL selection
                "fullscreen": 2,  # Disable fullscreen
                "mouselock": 2,  # Disable mouselock
                "mixed_script": 2,  # Disable mixed script
                "media_stream": 2,  # Disable media stream
                "media_stream_mic": 2,  # Disable mic
                "media_stream_camera": 2,  # Disable camera
                "protocol_handlers": 2,  # Disable protocol handlers
                "ppapi_broker": 2,  # Disable broker
                "automatic_downloads": 2,  # Disable automatic downloads
                "midi_sysex": 2,  # Disable midi
                "push_messaging": 2,  # Disable push
                "ssl_cert_decisions": 2,  # Disable SSL cert decisions
                "metro_switch_to_desktop": 2,  # Disable metro switch
                "protected_media_identifier": 2,  # Disable protected media
                "app_banner": 2,  # Disable app banner
                "site_engagement": 2,  # Disable site engagement
                "durable_storage": 2,  # Disable durable storage
            },
            "disk-cache-size": 4096,
            "profile.managed_default_content_settings.images": 2,
        }
        return prefs

    def cleanup(self):
        """Cleanup browser resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def init_driver(self):
        """Initialize optimized Chrome driver"""
        try:
            chrome_options = Options()

            # Basic headless setup
            if self.config["headless"]:
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--window-size=1920,1080")

            # Essential performance options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--disable-webgl")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-machine-learning-optimization-hints")
            chrome_options.add_argument("--disable-features=SharedArrayBuffer")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-machine-learning")
            chrome_options.add_argument("--disable-features=BlinkGenPropertyTrees")
            chrome_options.add_argument("--disable-gpu-compositing")
            chrome_options.add_argument(
                "--disable-component-extensions-with-background-pages"
            )
            chrome_options.add_argument("--disable-accelerated-2d-canvas")
            chrome_options.add_argument("--disable-accelerated-video")
            chrome_options.add_experimental_option(
                "excludeSwitches", ["enable-logging"]
            )

            # Memory optimization
            chrome_options.add_argument("--js-flags=--max-old-space-size=2048")
            chrome_options.add_argument("--memory-pressure-off")
            chrome_options.add_argument("--disk-cache-size=0")
            chrome_options.add_argument("--disable-dev-tools")
            chrome_options.add_argument("--disable-browser-side-navigation")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-translate")

            # Performance preferences
            prefs = {
                "profile.default_content_setting_values": {
                    "images": 2,
                    "plugins": 2,
                    "popups": 2,
                    "notifications": 2,
                },
                "disk-cache-size": 4096,
            }
            chrome_options.add_experimental_option("prefs", prefs)

            # User agent
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Create driver
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=chrome_options
            )

            # Set timeouts
            self.driver.set_page_load_timeout(self.config["page_load_timeout"])
            self.wait = WebDriverWait(self.driver, self.config["element_timeout"])

            # Initial JavaScript optimizations
            self.driver.execute_script(
                """
                // Disable console logging
                console.log = function() {};
                console.warn = function() {};
                console.error = function() {};

                // Disable analytics
                window.ga = function() {};
                window._gaq = [];

                // Clean up memory
                if (window.gc) { window.gc(); }
            """
            )

            return True

        except Exception as e:
            logger.error(f"Driver initialization failed: {str(e)}")
            raise ScraperException(f"Failed to initialize driver: {str(e)}")

    def handle_ad_frames(self) -> None:
        """Remove ad frames and overlays"""
        try:
            # Remove ad iframes
            self.driver.execute_script(
                """
                var elements = document.querySelectorAll('[id^="aswift_"], [id^="google_ads_"]');
                elements.forEach(e => e.remove());
            """
            )

            # Remove overlay elements
            self.driver.execute_script(
                """
                var overlays = document.querySelectorAll('[class*="overlay"], [class*="modal"]');
                overlays.forEach(e => e.remove());
            """
            )
        except Exception as e:
            logger.debug(f"Error handling ad frames: {str(e)}")

    @retry_on_exception(retries=2, delay=0.5)
    def safe_page_load(self, url: str) -> bool:
        """Safely load a page with retries"""
        try:
            self.driver.get(url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            self.handle_ad_frames()
            return True
        except Exception as e:
            logger.warning(f"Page load failed for {url}: {str(e)}")
            raise

    @retry_on_exception(retries=2, delay=0.5)
    def get_element_safely(
        self, by: By, selector: str, timeout: int = None
    ) -> Optional[Any]:
        """Safely get an element with explicit wait"""
        try:
            wait_time = timeout if timeout else self.config["element_timeout"]
            element = WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except Exception:
            return None

    @retry_on_exception(retries=3, delay=1)
    def get_apply_link(self, detail_url: str) -> str:
        try:
            self.remove_all_overlays()
            apply_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.pt-1 button"))
            )

            # Optimized click using JavaScript
            self.driver.execute_script("arguments[0].click();", apply_button)

            # Reduced wait for new window
            WebDriverWait(self.driver, 3).until(lambda d: len(d.window_handles) > 1)
            return self.get_new_window_url(detail_url)

        except Exception:
            return detail_url

    def get_new_window_url(self, fallback_url: str) -> str:
        """Handle new window/tab and get URL safely"""
        try:
            # Store original window
            original_window = self.driver.current_window_handle

            # Wait for new window
            WebDriverWait(self.driver, 5).until(lambda d: len(d.window_handles) > 1)

            # Switch to new window
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    self.driver.switch_to.window(window_handle)
                    # Wait for page load
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script("return document.readyState")
                        == "complete"
                    )
                    url = self.driver.current_url
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                    return url

            return fallback_url
        except Exception:
            return fallback_url

    def remove_all_overlays(self):
        """Comprehensive overlay and ad removal"""
        try:
            # Remove common ad iframes
            self.driver.execute_script(
                """
                function removeElements(selector) {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(e => e.remove());
                }
                
                // Remove ad iframes
                removeElements('[id^="aswift_"]');
                removeElements('[id^="google_ads_"]');
                
                // Remove overlay divs
                removeElements('[class*="overlay"]');
                removeElements('[class*="modal"]');
                removeElements('[class*="popup"]');
                
                // Remove fixed position elements
                const fixed = document.querySelectorAll('*');
                fixed.forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.position === 'fixed' || style.position === 'sticky') {
                        el.remove();
                    }
                });
            """
            )

            # Clear any remaining overlays
            self.driver.execute_script(
                """
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            """
            )
        except Exception as e:
            logger.debug(f"Error removing overlays: {str(e)}")

    @retry_on_exception(retries=2, delay=0.5)
    def extract_job_data(self, detail_url: str) -> Optional[Dict[str, Any]]:
        """Optimized job data extraction"""
        try:
            if not self.safe_page_load(detail_url):
                return None

            # Get all elements in one go to reduce DOM queries
            elements = {
                "time": self.get_element_safely(By.TAG_NAME, "time"),
                "title": self.get_element_safely(
                    By.XPATH, "//time/following-sibling::span//h1"
                ),
                "details": self.get_element_safely(
                    By.CSS_SELECTOR,
                    "div.flex.flex-wrap.my-3\\.5.gap-2.items-center.text-xs",
                ),
                "company": self.get_element_safely(
                    By.CSS_SELECTOR, "div.company-name, span.company-name"
                ),
                "location": self.get_element_safely(
                    By.CSS_SELECTOR, "div.location, span.location"
                ),
                "description": self.get_element_safely(
                    By.CSS_SELECTOR, "div.job-description, div.description"
                ),
            }

            if not elements["time"] or not elements["title"]:
                return None

            # Process date
            date_text = elements["time"].text.strip()
            posting_date = datetime.datetime.strptime(date_text, "%d %B %Y").date()

            # Check date validity
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            if posting_date not in [today, yesterday]:
                return None

            # Extract details
            details = {"job_type": "N/A", "salary": "N/A", "experience": "N/A"}
            if elements["details"]:
                spans = elements["details"].find_elements(By.TAG_NAME, "span")
                if len(spans) > 0:
                    details["job_type"] = spans[0].text.strip()
                if len(spans) > 1:
                    details["salary"] = spans[1].text.strip()
                if len(spans) > 2:
                    details["experience"] = spans[2].text.strip()

            return {
                "detail_url": detail_url,
                "job_title": elements["title"].text.strip(),
                "posting_date": posting_date.strftime("%d %B %Y"),
                "job_type": details["job_type"],
                "salary": details["salary"],
                "experience": details["experience"],
                "apply_link": self.get_apply_link(detail_url),
                "company_name": (
                    elements["company"].text.strip() if elements["company"] else "N/A"
                ),
                "location": (
                    elements["location"].text.strip() if elements["location"] else "N/A"
                ),
                "description": (
                    elements["description"].text.strip()
                    if elements["description"]
                    else "N/A"
                ),
            }

        except Exception as e:
            logger.error(f"Error extracting job data from {detail_url}: {str(e)}")
            return None

    @retry_on_exception()
    @log_execution_time
    def collect_job_urls(self) -> List[str]:
        """Collect all job URLs from the main page"""
        job_urls = []
        scroll_attempts = 0
        max_scroll_attempts = 2

        try:
            logger.info(f"Attempting to load URL: {JOB_PAGE_URL}")
            self.driver.get(JOB_PAGE_URL)
            while scroll_attempts < max_scroll_attempts:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(self.config["scroll_pause_time"])

                containers = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (
                            By.XPATH,
                            "//div[contains(@class, 'border-b') and contains(@class, 'rounded-lg')]",
                        )
                    )
                )

                for container in containers:
                    try:
                        url = (
                            WebDriverWait(container, 5)
                            .until(EC.presence_of_element_located((By.TAG_NAME, "a")))
                            .get_attribute("href")
                        )
                        if url and url not in job_urls:
                            job_urls.append(url)
                    except Exception:
                        continue

                scroll_attempts += 1

            return job_urls[: self.config["max_jobs"]]

        except Exception as e:
            logger.error(f"Error collecting job URLs: {str(e)}")
            raise ScraperException(f"Failed to collect job URLs: {str(e)}")

    @log_execution_time
    def cleanup_memory(self, full_cleanup: bool = False):
        """Optimized memory cleanup"""
        try:
            if not self.driver:
                return

            if full_cleanup:
                # Full cleanup only between batches
                self.driver.execute_script(
                    """
                    window.performance.memory.usedJSHeapSize = 0;
                    window.performance.memory.totalJSHeapSize = 0;
                    window.localStorage.clear();
                    window.sessionStorage.clear();
                    let cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        let cookie = cookies[i];
                        let eqPos = cookie.indexOf('=');
                        let name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
                        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT';
                    }
                    if (window.gc) { window.gc(); }
                """
                )
                self.driver.delete_all_cookies()
            else:
                # Light cleanup for regular operations
                self.driver.execute_script(
                    """
                    if (window.gc) { window.gc(); }
                    const elements = document.querySelectorAll('[class*="overlay"], [class*="modal"], [class*="popup"]');
                    elements.forEach(e => e.remove());
                """
                )

        except Exception as e:
            logger.debug(f"Memory cleanup error: {str(e)}")

    @retry_on_exception()
    @log_execution_time
    def scrape_jobs(self) -> List[Dict[str, Any]]:
        """Main job scraping function"""
        try:
            if not self.init_driver():
                raise ScraperException("Failed to initialize driver")

            logger.info(f"Accessing {JOB_PAGE_URL}")

            # Load main page
            self.driver.get(JOB_PAGE_URL)

            if not self.safe_page_load(JOB_PAGE_URL):
                raise ScraperException("Failed to load main page")

            job_urls = self.collect_job_urls()
            logger.info(f"Found {len(job_urls)} job URLs")

            scraped_jobs = []
            batch_size = self.config["batch_size"]
            for i in range(0, len(job_urls), batch_size):
                batch = job_urls[i : i + batch_size]
                batch_jobs = []

                try:
                    for url in batch:
                        try:

                            job_data = self.extract_job_data(url)
                            if job_data:
                                batch_jobs.append(job_data)
                                logger.info(
                                    f"Successfully scraped job: {job_data['job_title']}"
                                )

                        except Exception as e:
                            logger.error(f"Error processing job {url}: {str(e)}")
                            continue

                        # Small delay between jobs
                        time.sleep(0.5)

                    scraped_jobs.extend(batch_jobs)

                    # Full cleanup only after batch completion
                    # if i + batch_size < len(job_urls):
                    #     self.cleanup_memory(full_cleanup=True)
                    #     self.driver.quit()
                    #     self.init_driver()

                except Exception as batch_error:
                    logger.error(f"Error processing batch: {str(batch_error)}")
                    continue

            return scraped_jobs

        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}\n{traceback.format_exc()}")
            raise ScraperException(f"Job scraping failed: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()


@retry_on_exception()
@log_execution_time
async def scrape_and_process_jobs():
    logger.info(f"Starting job scraping at {datetime.datetime.now()}")
    db = SessionLocal()
    history_record = None

    try:
        # Create history record
        history_record = ScrapingHistory(start_time=datetime.datetime.now(IST))
        db.add(history_record)
        db.commit()

        # Initialize scraper with db session
        scraper = JobScraper(db=db)
        scraped_jobs = scraper.scrape_jobs()

        if not scraped_jobs:
            logger.info("No jobs found from scraping")
            history_record.status = "success"
            history_record.jobs_found = 0
            history_record.end_time = datetime.datetime.now(IST)
            await send_email_report(
                "Job Scraping Report - No Jobs Found",
                "email/job_report.html",
                {"jobs": [], "date": datetime.date.today()},
                db,
            )
            return {"status": "success", "message": "No jobs found"}

        logger.info(f"Found {len(scraped_jobs)} jobs from scraping")

        try:
            logger.info("Storing jobs in database...")

            # Filter out existing jobs
            new_jobs = []
            for job_data in scraped_jobs:
                existing_job = scraper.get_by_url(job_data["detail_url"])
                if not existing_job:
                    new_jobs.append(job_data)

            logger.info(f"Found {len(new_jobs)} new jobs to store")

            if new_jobs:
                stored_jobs = await scraper.store_jobs(new_jobs)
                logger.info(f"Successfully stored {len(stored_jobs)} new jobs")

                # Get the actual Job objects from database for LinkedIn format
                job_objects = [
                    scraper.get_by_url(job["detail_url"])
                    for job in stored_jobs
                    if scraper.get_by_url(job["detail_url"])
                ]

                # Create LinkedIn format using the Job objects
                linkedin_format = create_linkedin_format(job_objects)

                # Update history record
                history_record.jobs_found = len(stored_jobs)
                history_record.status = "success"
                history_record.end_time = datetime.datetime.now(IST)

                # Send email report
                await send_email_report(
                    f"Job Scraping Report - {len(stored_jobs)} New Jobs",
                    "email/job_report.html",
                    {
                        "jobs": job_objects,  # Use Job objects instead of dictionaries
                        "date": datetime.date.today(),
                        "linkedin_format": linkedin_format,
                    },
                    db,
                )
                return {
                    "status": "success",
                    "message": f"Stored {len(stored_jobs)} new jobs",
                    "jobs_found": str(len(stored_jobs)),
                }
            else:
                logger.info("No new jobs to store")
                history_record.status = "success"
                history_record.jobs_found = 0
                history_record.end_time = datetime.datetime.now(IST)
                await send_email_report(
                    "Job Scraping Report - No New Jobs",
                    "email/job_report.html",
                    {"jobs": [], "date": datetime.date.today()},
                    db,
                )
                return {"status": "success", "message": "No new jobs to store"}

        except Exception as e:
            error_msg = f"Error in scrape_and_process_jobs: {str(e)}"
            logger.error(error_msg)
            if history_record:
                history_record.status = "failed"
                history_record.error = str(e)
                history_record.end_time = datetime.datetime.now(IST)
            try:
                await send_email_report(
                    "Job Scraping Error Report",
                    "email/error_report.html",
                    {"error": error_msg, "date": datetime.date.today()},
                    db,
                )
            except Exception as email_error:
                logger.error(f"Failed to send error report email: {str(email_error)}")
            raise

    finally:
        if history_record:
            db.commit()
        db.close()
