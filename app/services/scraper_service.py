import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
from typing import List, Dict, Any
import pytz


from ..models.scraping_history import ScrapingHistory
from ..utils.linkedin_formatter import create_linkedin_format
from ..db.repositories.job_repository import JobRepository
from ..services.email_service import send_email_report
from ..db.session import SessionLocal
from ..core.config import get_settings
from ..core.constants import JOB_PAGE_URL, DEFAULT_WAIT
from ..utils.exceptions import ScraperException
from ..utils.decorators import retry_on_exception, log_execution_time

settings = get_settings()

IST = pytz.timezone("Asia/Kolkata")


def init_driver():
    """Initialize a headless Chrome driver."""
    try:
        chrome_options = Options()
        if settings.SELENIUM_HEADLESS:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument(
            "--disable-features=IsolateOrigins,site-per-process"
        )
        # Add these options to handle WebGL warning
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-webgl2")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(settings.SELENIUM_TIMEOUT)
        return driver
    except Exception as e:
        raise ScraperException(f"Failed to initialize driver: {str(e)}")


def dismiss_ads(driver):
    """Attempt to dismiss popup ads."""
    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                    "'abcdefghijklmnopqrstuvwxyz'), 'close')]",
                )
            )
        )
        close_button.click()
        logger.info("Popup dismissed")
    except Exception:
        logger.debug("No popup found or failed to dismiss")


@retry_on_exception()
@log_execution_time
async def scrape_jobs() -> List[Dict[str, Any]]:
    """Scrape jobs from the website."""
    driver = None
    today_jobs = []
    yesterday_jobs = []
    max_jobs = 20

    try:
        driver = init_driver()
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        logger.info(f"Accessing {JOB_PAGE_URL}")
        driver.get(JOB_PAGE_URL)
        WebDriverWait(driver, DEFAULT_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        dismiss_ads(driver)

        # Get job URLs
        logger.info("Collecting job URLs...")
        job_urls = []  # Using list to maintain order

        # Scroll and collect URLs
        scroll_attempts = 0
        max_scroll_attempts = 3

        while scroll_attempts < max_scroll_attempts:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            containers = WebDriverWait(driver, DEFAULT_WAIT).until(
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

        logger.info(f"Found {len(job_urls)} job URLs")

        # Process each URL until we have enough jobs
        processed_count = 0
        jobs_found = False

        for detail_url in job_urls:
            if processed_count >= max_jobs:
                logger.info(f"Reached target of {max_jobs} jobs. Stopping collection.")
                break

            try:
                logger.info(f"Processing job detail page: {detail_url}")
                driver.get(detail_url)

                # Wait for page load with timeout
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except TimeoutException:
                    logger.warning(f"Page load timeout for {detail_url}, skipping...")
                    continue

                dismiss_ads(driver)

                # Get posting date
                try:
                    time_elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "time"))
                    )
                    date_text = time_elem.text.strip()
                    posting_date = datetime.datetime.strptime(
                        date_text, "%d %B %Y"
                    ).date()

                    # If the job is not from today or yesterday, skip
                    if posting_date not in [today, yesterday]:
                        logger.debug(
                            f"Skipping job. Posting date ({posting_date}) is not today or yesterday."
                        )

                        # If we've already found some jobs and this one is older, stop processing
                        if jobs_found:
                            logger.info(
                                "Found older job after processing current jobs. Stopping collection."
                            )
                            break

                        continue

                    jobs_found = True  # We found a relevant job

                except (TimeoutException, ValueError) as e:
                    logger.warning(f"Error getting posting date: {str(e)}")
                    continue

                # Get job title
                title_elem = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//time/following-sibling::span//h1")
                    )
                )
                job_title = title_elem.text.strip()

                # Get apply link
                apply_link = detail_url  # Default fallback
                try:
                    # Find and click the apply button
                    apply_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.pt-1 button"))
                    )

                    # Store the current window handle
                    main_window = driver.current_window_handle

                    # Click the button (this should open a new tab)
                    apply_button.click()

                    # Wait for new window/tab to open
                    WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)

                    # Switch to the new tab
                    new_window = [
                        handle
                        for handle in driver.window_handles
                        if handle != main_window
                    ][0]
                    driver.switch_to.window(new_window)

                    # Wait for the new page to load and get its URL
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )

                    # Get the URL from the new tab
                    apply_link = driver.current_url
                    logger.info(f"Found apply link: {apply_link}")

                    # Close the new tab and switch back to the main window
                    driver.close()
                    driver.switch_to.window(main_window)
                except Exception as e:
                    logger.warning(f"Error getting apply link: {str(e)}")

                # Get job details
                try:
                    details_container = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                "div.flex.flex-wrap.my-3\\.5.gap-2.items-center.text-xs",
                            )
                        )
                    )
                    spans = details_container.find_elements(By.TAG_NAME, "span")
                    job_type = spans[0].text.strip() if len(spans) > 0 else "N/A"
                    salary = spans[1].text.strip() if len(spans) > 1 else "N/A"
                    experience = spans[2].text.strip() if len(spans) > 2 else "N/A"
                except Exception:
                    job_type = salary = experience = "N/A"

                # Get company name
                company_name = None
                try:
                    company_elem = driver.find_element(
                        By.CSS_SELECTOR, "div.company-name, span.company-name"
                    )
                    company_name = company_elem.text.strip()
                except NoSuchElementException:
                    pass

                # Get location
                location = None
                try:
                    location_elem = driver.find_element(
                        By.CSS_SELECTOR, "div.location, span.location"
                    )
                    location = location_elem.text.strip()
                except NoSuchElementException:
                    pass

                # Get description
                description = None
                try:
                    desc_elem = driver.find_element(
                        By.CSS_SELECTOR, "div.job-description, div.description"
                    )
                    description = desc_elem.text.strip()
                except NoSuchElementException:
                    pass

                # Create job data dictionary
                job_data = {
                    "detail_url": detail_url,
                    "job_title": job_title,
                    "posting_date": posting_date.strftime("%d %B %Y"),
                    "job_type": job_type,
                    "salary": salary,
                    "experience": experience,
                    "apply_link": apply_link,
                    "company_name": company_name,
                    "location": location,
                    "description": description,
                }

                # Add to appropriate list based on posting date
                if posting_date == today:
                    today_jobs.append(job_data)
                    logger.info(f"Added today's job: {job_title}")
                elif posting_date == yesterday:
                    yesterday_jobs.append(job_data)
                    logger.info(f"Added yesterday's job: {job_title}")

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing job {detail_url}: {str(e)}")
                continue

            time.sleep(1)  # Small delay between jobs

        # Combine today's and yesterday's jobs
        all_jobs = today_jobs + yesterday_jobs
        final_jobs = all_jobs[:max_jobs]

        logger.info(
            f"Successfully scraped {len(final_jobs)} jobs "
            f"(Today: {len(today_jobs)}, Yesterday: {len(yesterday_jobs)})"
        )
        return final_jobs

    except Exception as e:
        error_msg = f"Failed to scrape jobs: {str(e)}"
        logger.error(error_msg)
        raise ScraperException(error_msg)
    finally:
        if driver:
            driver.quit()


@log_execution_time
async def scrape_and_process_jobs():
    """Main function to scrape and process jobs."""
    logger.info(f"Starting job scraping at {datetime.datetime.now()}")
    db = SessionLocal()
    history_record = None

    try:
        # Create history record
        history_record = ScrapingHistory(start_time=datetime.datetime.now(IST))
        db.add(history_record)
        db.commit()

        # Scrape jobs
        logger.info("Starting job scraping...")
        scraped_jobs = await scrape_jobs()

        if not scraped_jobs:
            logger.info("No jobs found from scraping")
            # Update history record
            history_record.status = "success"
            history_record.jobs_found = 0
            history_record.end_time = datetime.datetime.now(IST)
            await send_email_report(
                "Job Scraping Report - No Jobs Found",
                "email/job_report.html",
                {"jobs": [], "date": datetime.date.today()},
                db,
            )
            return

        logger.info(f"Found {len(scraped_jobs)} jobs from scraping")

        try:
            logger.info("Storing jobs in database...")
            repo = JobRepository(db)

            # Filter out existing jobs
            new_jobs = []
            for job_data in scraped_jobs:
                existing_job = repo.get_by_url(job_data["detail_url"])
                if not existing_job:
                    new_jobs.append(job_data)

            logger.info(f"Found {len(new_jobs)} new jobs to store")

            if new_jobs:
                stored_jobs = await repo.store_jobs(new_jobs)
                logger.info(f"Successfully stored {len(stored_jobs)} new jobs")

                # Create LinkedIn format
                linkedin_format = create_linkedin_format(stored_jobs)

                # Update history record
                history_record.jobs_found = len(stored_jobs)
                history_record.status = "success"
                history_record.end_time = datetime.datetime.now(IST)

                # Send email report
                await send_email_report(
                    f"Job Scraping Report - {len(stored_jobs)} New Jobs",
                    "email/job_report.html",
                    {
                        "jobs": stored_jobs,
                        "date": datetime.date.today(),
                        "linkedin_format": linkedin_format,
                    },
                    db,
                )
            else:
                logger.info("No new jobs to store")
                # Update history record
                history_record.status = "success"
                history_record.jobs_found = 0
                history_record.end_time = datetime.datetime.now(IST)
                await send_email_report(
                    "Job Scraping Report - No New Jobs",
                    "email/job_report.html",
                    {"jobs": [], "date": datetime.date.today()},
                    db,
                )

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
