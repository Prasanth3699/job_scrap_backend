from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models.job import Job
from ..models.scraping_history import ScrapingHistory
from ..core.logger import logger


class StatsService:
    @staticmethod
    def get_dashboard_stats(db: Session):
        try:
            # Get today's date
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            # Get basic stats
            total_jobs = db.query(Job).count()
            today_jobs = (
                db.query(Job).filter(func.date(Job.created_at) == today).count()
            )
            print(today_jobs)

            # Get latest scraping session
            latest_scrape = (
                db.query(ScrapingHistory)
                .order_by(ScrapingHistory.start_time.desc())
                .first()
            )

            # Calculate success rate
            recent_scrapes = (
                db.query(ScrapingHistory)
                .filter(ScrapingHistory.start_time >= today - timedelta(days=7))
                .all()
            )
            success_count = sum(1 for s in recent_scrapes if s.status == "success")
            success_rate = (
                (success_count / len(recent_scrapes) * 100) if recent_scrapes else 0
            )

            # Get jobs by category
            jobs_by_category = (
                db.query(Job.job_type, func.count(Job.id).label("count"))
                .group_by(Job.job_type)
                .all()
            )

            # Get scraping history
            scraping_history = (
                db.query(ScrapingHistory)
                .order_by(ScrapingHistory.start_time.desc())
                .limit(10)
                .all()
            )

            # Calculate average scrape time
            avg_scrape_time = "N/A"
            if latest_scrape and latest_scrape.end_time:
                duration = latest_scrape.end_time - latest_scrape.start_time
                print(duration)
                avg_scrape_time = f"{duration.total_seconds():.1f}s"

            return {
                "stats": {
                    "todayJobs": today_jobs,
                    "totalJobs": total_jobs,
                    "successRate": round(success_rate, 1),
                    "avgScrapeTime": avg_scrape_time,
                    "lastScrapeTime": (
                        latest_scrape.end_time.isoformat()
                        if latest_scrape and latest_scrape.end_time
                        else None
                    ),
                },
                "jobsByCategory": [
                    {"name": category or "Other", "value": count}
                    for category, count in jobs_by_category
                ],
                "successRate": [
                    {"name": "Success", "value": success_rate},
                    {"name": "Failed", "value": 100 - success_rate},
                ],
                "scrapingHistory": [
                    {
                        "id": history.id,
                        "start_time": history.start_time.isoformat(),
                        "end_time": (
                            history.end_time.isoformat() if history.end_time else None
                        ),
                        "jobs_found": history.jobs_found,
                        "status": history.status,
                        "error": history.error,
                    }
                    for history in scraping_history
                ],
            }
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            raise
