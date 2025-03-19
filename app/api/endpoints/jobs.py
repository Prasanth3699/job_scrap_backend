from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel
from app.tasks import run_scraping_job
from ...utils.task_lock import RedisLock
from ...db.session import get_db
from ...services.scraper_service import scrape_and_process_jobs
from ...schemas.job import JobResponse
from ...db.repositories.job_repository import JobRepository
from ...core.constants import DEFAULT_LIMIT, DEFAULT_OFFSET
from loguru import logger
from app.core.redis_lock import redis_lock_manager


router = APIRouter()


# @router.post("/scrape", response_model=Dict[str, str])
# async def trigger_scrape(source_id: Optional[int] = None):
#     """Trigger job scraping manually through Celery"""
#     lock_name = f"scraping_task:{source_id if source_id else 'all'}"

#     try:
#         # Check if task is already running
#         if RedisLock.is_locked(lock_name):
#             raise HTTPException(
#                 status_code=409, detail="A scraping task is already in progress"
#             )

#         task = run_scraping_job.delay(source_id)

#         return {
#             "status": "success",
#             "message": f"Scraping job has been queued for source {source_id if source_id else 'all'}",
#             "task_id": task.id,
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error triggering scrape: {str(e)}")
#         raise HTTPException(status_code=500, detail="Failed to queue scraping job")


@router.post("/scrape", response_model=Dict[str, str])
async def trigger_scrape(source_id: Optional[int] = None, force: bool = False):
    lock_name = f"scraping_task:{source_id if source_id else 'all'}"

    try:
        # If force is True, release any existing lock
        if force:
            redis_lock_manager.release_lock(lock_name)

        # Try to acquire the lock
        if not redis_lock_manager.acquire_lock(lock_name):
            raise HTTPException(
                status_code=409,
                detail="A scraping task is already in progress. Use ?force=true to override.",
            )

        try:
            # Run the scraping job
            task = run_scraping_job.delay(source_id)

            return {
                "status": "success",
                "message": f"Scraping job has been queued for source {source_id if source_id else 'all'}",
                "task_id": task.id,
            }
        except Exception as job_error:
            # If job fails, release the lock
            redis_lock_manager.release_lock(lock_name)
            raise

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering scrape: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue scraping job")


class JobsResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    hasMore: bool


@router.get("", response_model=JobsResponse)
async def get_jobs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=100),
    search: Optional[str] = None,
    location: Optional[List[str]] = Query(None),
    job_type: Optional[List[str]] = Query(None),
    experience: Optional[List[str]] = Query(None),
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
):
    """Get jobs with filters and pagination"""
    try:
        repo = JobRepository(db)
        skip = (page - 1) * limit

        # Get filtered jobs
        jobs, total = repo.get_filtered_jobs(
            skip=skip,
            limit=limit + 1,  # Get one extra to check if there are more
            search=search,
            location=location,
            job_type=job_type,
            experience=experience,
            salary_min=salary_min,
            salary_max=salary_max,
        )

        # Check if there are more results
        has_more = len(jobs) > limit
        jobs = jobs[:limit]  # Remove the extra item

        return JobsResponse(jobs=jobs, total=total, hasMore=has_more)
    except Exception as e:
        logger.error(f"Error getting jobs: {str(e)}")
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


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job by ID"""
    repo = JobRepository(db)
    job = repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/related", response_model=List[JobResponse])
async def get_related_jobs(
    job_id: int, limit: int = Query(3, ge=1, le=10), db: Session = Depends(get_db)
):
    """Get related jobs based on current job"""
    repo = JobRepository(db)
    current_job = repo.get_by_id(job_id)
    if not current_job:
        raise HTTPException(status_code=404, detail="Job not found")

    related_jobs = repo.get_related_jobs(current_job, limit)
    return related_jobs
