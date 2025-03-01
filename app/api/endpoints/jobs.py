from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.tasks import run_scraping_job
from ...utils.task_lock import RedisLock
from ...db.session import get_db
from ...services.scraper_service import scrape_and_process_jobs
from ...schemas.job import JobResponse
from ...db.repositories.job_repository import JobRepository
from ...core.constants import DEFAULT_LIMIT, DEFAULT_OFFSET
from loguru import logger

router = APIRouter()


@router.post("/scrape", response_model=Dict[str, str])
async def trigger_scrape(source_id: Optional[int] = None):
    """Trigger job scraping manually through Celery"""
    lock_name = f"scraping_task:{source_id if source_id else 'all'}"

    try:
        # Check if task is already running
        if RedisLock.is_locked(lock_name):
            raise HTTPException(
                status_code=409, detail="A scraping task is already in progress"
            )

        task = run_scraping_job.delay(source_id)

        return {
            "status": "success",
            "message": f"Scraping job has been queued for source {source_id if source_id else 'all'}",
            "task_id": task.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering scrape: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue scraping job")


# @router.post("/scrape", response_model=dict)
# async def trigger_scrape(
#     background_tasks: BackgroundTasks, db: Session = Depends(get_db)
# ):
#     """Trigger job scraping manually"""
#     try:
#         await background_tasks.add_task(scrape_and_process_jobs)
#         return {"message": "Job scraping started", "status": "success"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[JobResponse])
async def get_jobs(
    db: Session = Depends(get_db),
    skip: int = Query(DEFAULT_OFFSET, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=100),
):
    """Get scraped jobs"""
    try:
        repo = JobRepository(db)
        return repo.get_jobs(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent", response_model=List[JobResponse])
async def get_recent_jobs(
    db: Session = Depends(get_db), days: int = Query(1, ge=1, le=30)
):
    """Get recent jobs from the last N days"""
    try:
        repo = JobRepository(db)
        return repo.get_recent_jobs(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job by ID"""
    repo = JobRepository(db)
    job = repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
