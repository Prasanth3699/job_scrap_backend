import datetime
import re
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


from ..services.job_source_service import JobSourceService
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


class JobScraper:

    def __init__(self, db: Session, source_url: str = None):
        self.driver = None
        self.wait = None
        self.config = SCRAPER_CONFIG
        self.db = db
        self.source_url = source_url or self.source_url

    def get_by_url(self, url: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.detail_url == url).first()

    def store_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        """Enhanced job data extraction with HTML description and better company name extraction"""
        try:
            if not self.safe_page_load(detail_url):
                return None

            # Get all elements in one go
            elements = {
                "time": self.get_element_safely(By.TAG_NAME, "time"),
                "title_element": self.get_element_safely(
                    By.XPATH, "//time/following-sibling::span//h1"
                ),
                "details": self.get_element_safely(
                    By.CSS_SELECTOR,
                    "div.flex.flex-wrap.my-3\\.5.gap-2.items-center.text-xs",
                ),
                "description_container": self.get_element_safely(
                    By.XPATH,
                    "//time/following-sibling::span[2]//div[contains(@class, 'prose')]",
                ),
            }

            if not elements["time"] or not elements["title_element"]:
                return None

            # Process date
            date_text = elements["time"].text.strip()
            posting_date = datetime.datetime.strptime(date_text, "%d %B %Y").date()

            # Check date validity
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            if posting_date not in [today, yesterday]:
                return None

            # Extract full title
            full_title = elements["title_element"].text.strip()

            # Extract company name from title
            company_name = self.extract_company_name(full_title)

            # Extract location from title
            title_parts = full_title.split("|")
            location = title_parts[1].strip() if len(title_parts) > 1 else "N/A"

            # Clean job title - remove company name and "is hiring for" part
            job_title = full_title.split("|")[0] if "|" in full_title else full_title
            job_title = (
                job_title.replace(company_name, "").replace("is hiring for", "").strip()
            )

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

            # Get complete HTML content of description
            description_html = self.get_description_html(
                elements["description_container"]
            )

            return {
                "detail_url": detail_url,
                "job_title": job_title,
                "posting_date": posting_date.strftime("%d %B %Y"),
                "job_type": details["job_type"],
                "salary": details["salary"],
                "experience": details["experience"],
                "apply_link": self.get_apply_link(detail_url),
                "company_name": company_name,
                "location": location,
                "description": description_html,
            }

        except Exception as e:
            logger.error(f"Error extracting job data from {detail_url}: {str(e)}")
            return None

    def extract_company_name(self, title: str) -> str:
        """Extract company name from job title"""
        try:
            # Split title by "is hiring"
            if "is hiring" in title:
                company_name = title.split("is hiring")[0].strip()
                return company_name
            return "N/A"
        except Exception as e:
            logger.error(f"Error extracting company name: {str(e)}")
            return "N/A"

    def get_description_html(self, description_container) -> str:
        """Get the HTML content with a simpler, more reliable approach"""
        try:
            if not description_container:
                return "N/A"

            # Get the HTML directly without JavaScript
            description_html = description_container.get_attribute("outerHTML")

            if not description_html:
                return "N/A"

            # Clean the HTML using a simpler JavaScript approach
            clean_html = self.driver.execute_script(
                """
                function cleanHTML(html) {
                    const div = document.createElement('div');
                    div.innerHTML = arguments[0];
                    
                    // Remove script tags
                    const scripts = div.getElementsByTagName('script');
                    while(scripts.length > 0) {
                        scripts[0].parentNode.removeChild(scripts[0]);
                    }
                    
                    // Remove style tags
                    const styles = div.getElementsByTagName('style');
                    while(styles.length > 0) {
                        styles[0].parentNode.removeChild(styles[0]);
                    }
                    
                    // Remove all classes and ids
                    const elements = div.getElementsByTagName('*');
                    for(let el of elements) {
                        el.removeAttribute('class');
                        el.removeAttribute('id');
                    }
                    
                    return div.innerHTML;
                }
                return cleanHTML(arguments[0]);
                """,
                description_html,
            )

            if not clean_html or clean_html in ["undefined", "null", ""]:
                # Fallback to plain text
                return f"<div>{description_container.text}</div>"

            return f"<div>{clean_html}</div>"

        except Exception as e:
            logger.error(f"Error getting description HTML: {str(e)}")
            try:
                # Fallback to plain text
                return f"<div>{description_container.text}</div>"
            except:
                return "N/A"

    @retry_on_exception()
    @log_execution_time
    def collect_job_urls(self) -> List[str]:
        """Collect all job URLs from the main page"""
        job_urls = []
        scroll_attempts = 0
        max_scroll_attempts = 2

        try:
            logger.info(f"Attempting to load URL: {self.source_url}")
            self.driver.get(self.source_url)
            while scroll_attempts < max_scroll_attempts:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(self.config["scroll_pause_time"])

                containers = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (
                            By.XPATH,
                            "//a[contains(@class, 'relative') and contains(@class, 'lg:w-64')]",
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

            logger.info(f"Accessing {self.source_url}")

            # Load main page
            self.driver.get(self.source_url)

            if not self.safe_page_load(self.source_url):
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
def scrape_and_process_jobs(source_id: Optional[int] = None):
    logger.info(
        f"Starting job scraping at {datetime.datetime.now()} for source_id: {source_id}"
    )

    db = None
    history_record = None

    try:
        db = SessionLocal()

        # Get job sources to scrape
        if source_id:
            source = JobSourceService.get_source_by_id(db, source_id)
            if not source:
                raise ValueError(f"Job source with ID {source_id} not found")
            sources = [source]
            logger.info(f"Scraping single source: {source.name} (ID: {source.id})")
        else:
            sources = JobSourceService.get_active_sources(db)
            logger.info(f"Found {len(sources)} active sources to scrape")

        if not sources:
            logger.warning("No active sources found to scrape")
            return {
                "status": "success",
                "message": "No active sources found to scrape",
                "jobs_found": "0",
            }

        total_new_jobs = 0
        all_stored_jobs = []
        last_scraper = None  # Keep track of last scraper instance

        for source in sources:
            try:
                # Create history record for this source
                history_record = ScrapingHistory(
                    start_time=datetime.datetime.now(IST), source_id=source.id
                )
                db.add(history_record)
                db.commit()

                logger.info(f"Processing source: {source.name} (ID: {source.id})")

                # Initialize scraper with source URL
                scraper = JobScraper(db=db, source_url=source.url)
                last_scraper = scraper  # Store reference to current scraper
                scraped_jobs = scraper.scrape_jobs()

                if not scraped_jobs:
                    logger.info(f"No jobs found from scraping source: {source.name}")
                    history_record.status = "success"
                    history_record.jobs_found = 0
                    history_record.end_time = datetime.datetime.now(IST)
                    db.commit()
                    continue

                logger.info(
                    f"Found {len(scraped_jobs)} jobs from scraping source: {source.name}"
                )

                try:
                    # Filter out existing jobs
                    new_jobs = [
                        job_data
                        for job_data in scraped_jobs
                        if not scraper.get_by_url(job_data["detail_url"])
                    ]

                    logger.info(
                        f"Found {len(new_jobs)} new jobs to store from source: {source.name}"
                    )

                    if new_jobs:
                        stored_jobs = scraper.store_jobs(new_jobs)
                        total_new_jobs += len(stored_jobs)
                        all_stored_jobs.extend(stored_jobs)

                        # Update history record
                        history_record.jobs_found = len(stored_jobs)
                        history_record.status = "success"
                        history_record.end_time = datetime.datetime.now(IST)
                    else:
                        history_record.status = "success"
                        history_record.jobs_found = 0
                        history_record.end_time = datetime.datetime.now(IST)

                    # Update source last scraped timestamp
                    source.last_scraped_at = datetime.datetime.now(IST)
                    db.commit()

                except Exception as e:
                    error_msg = (
                        f"Error processing jobs for source {source.name}: {str(e)}"
                    )
                    logger.error(error_msg)
                    history_record.status = "failed"
                    history_record.error = str(e)
                    history_record.end_time = datetime.datetime.now(IST)
                    db.commit()
                    continue

            except Exception as e:
                logger.error(f"Error scraping source {source.name}: {str(e)}")
                if history_record:
                    history_record.status = "failed"
                    history_record.error = str(e)
                    history_record.end_time = datetime.datetime.now(IST)
                    db.commit()
                continue

            finally:
                if scraper and scraper.driver:
                    scraper.driver.quit()

        # Handle email reports
        try:
            if total_new_jobs > 0 and last_scraper:
                # Get the actual Job objects
                job_objects = [
                    last_scraper.get_by_url(job["detail_url"])
                    for job in all_stored_jobs
                    if last_scraper.get_by_url(job["detail_url"])
                ]

                linkedin_format = create_linkedin_format(job_objects)

                send_email_report(
                    f"Job Scraping Report - {total_new_jobs} New Jobs",
                    "email/job_report.html",
                    {
                        "jobs": job_objects,
                        "date": datetime.date.today(),
                        "linkedin_format": linkedin_format,
                    },
                    db,
                )
            else:
                send_email_report(
                    "Job Scraping Report - No New Jobs",
                    "email/job_report.html",
                    {"jobs": [], "date": datetime.date.today()},
                    db,
                )
        except Exception as email_error:
            logger.error(f"Failed to send email report: {str(email_error)}")

        return {
            "status": "success",
            "message": f"Stored {total_new_jobs} new jobs",
            "jobs_found": str(total_new_jobs),
        }

    except Exception as e:
        error_msg = f"Error in scrape_and_process_jobs: {str(e)}"
        logger.error(error_msg)
        if history_record:
            history_record.status = "failed"
            history_record.error = str(e)
            history_record.end_time = datetime.datetime.now(IST)
            if db:
                db.commit()
        if db:
            try:
                send_email_report(
                    "Job Scraping Error Report",
                    "email/error_report.html",
                    {"error": error_msg, "date": datetime.date.today()},
                    db,
                )
            except Exception as email_error:
                logger.error(f"Failed to send error report email: {str(email_error)}")
        raise

    finally:
        if db:
            try:
                if history_record:
                    db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")
