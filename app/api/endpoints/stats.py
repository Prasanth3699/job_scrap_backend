from datetime import datetime, timedelta

from sqlalchemy import func
from ...models.scraping_history import ScrapingHistory
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from loguru import logger
from ...services.stats_service import StatsService

# from ...schemas.stats import ScrapingHistory
from ...models.job import Job

router = APIRouter()


@router.get("/dashboard-stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    return StatsService.get_dashboard_stats(db)


@router.get("/scraping-history")
async def get_scraping_history(db: Session = Depends(get_db)):
    try:
        # Get recent sessions
        recent_sessions = (
            db.query(ScrapingHistory)
            .order_by(ScrapingHistory.start_time.desc())
            .limit(10)
            .all()
        )

        # Get jobs over time (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        jobs_over_time = (
            db.query(
                func.date(Job.created_at).label("date"),
                func.count(Job.id).label("count"),
            )
            .filter(Job.created_at >= thirty_days_ago)
            .group_by(func.date(Job.created_at))
            .order_by(func.date(Job.created_at))
            .all()
        )

        return {
            "recentSessions": [
                {
                    "id": session.id,
                    "startTime": session.start_time.isoformat(),
                    "endTime": (
                        session.end_time.isoformat() if session.end_time else None
                    ),
                    "jobsScraped": session.jobs_found,
                    "status": session.status,
                    "error": session.error,
                }
                for session in recent_sessions
            ],
            "jobsOverTime": [
                {
                    "date": date.isoformat() if isinstance(date, datetime) else date,
                    "count": count,
                }
                for date, count in jobs_over_time
            ],
        }
    except Exception as e:
        logger.error(f"Error getting scraping history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
