from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...db.session import get_db
from ...services.scraper_service import scrape_and_process_jobs
from ...schemas.job import JobResponse
from ...db.repositories.job_repository import JobRepository
from ...core.constants import DEFAULT_LIMIT, DEFAULT_OFFSET

# from ...tasks.scraping_tasks import run_scraping_workflow
# from ...core.celery_config import celery_app

from celery.result import AsyncResult
from ...tasks.scraping_tasks import scrape_jobs_task
from ...utils.response_schemas import (
    ScrapeResponse,
    TaskStatusResponse,
    TaskErrorResponse,
)

router = APIRouter()


# ----------------------------------------


@router.post("/scrape")
async def trigger_scrape():
    try:
        task = scrape_jobs_task.delay()
        return {
            "message": "Job scraping started",
            "task_id": task.id,
            "status": "pending",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/scrape", response_model=ScrapeResponse)
# async def trigger_scrape(db: Session = Depends(get_db)) -> Dict:
#     """
#     Trigger job scraping manually
#     """
#     try:
#         # Launch Celery task
#         task = scrape_jobs_task.delay()

#         return {
#             "message": "Job scraping started",
#             "status": "success",
#             "task_id": task.id,
#         }
#     except Exception as e:
#         raise HTTPException(
#             status_code=500, detail=f"Failed to start scraping task: {str(e)}"
#         )


# @router.get("/scrape/status/{task_id}", response_model=TaskStatusResponse)
# async def get_task_status(task_id: str) -> Dict:
#     """
#     Get the status of a scraping task
#     """
#     try:
#         task_result = AsyncResult(task_id, app=celery_app)

#         response = {
#             "task_id": task_id,
#             "status": task_result.status,
#             "result": task_result.result if task_result.ready() else None,
#         }

#         if task_result.failed():
#             response["error"] = str(task_result.result)

#         return response
#     except Exception as e:
#         raise HTTPException(
#             status_code=500, detail=f"Failed to get task status: {str(e)}"
#         )


# @router.delete("/scrape/cancel/{task_id}", response_model=Dict)
# async def cancel_task(task_id: str) -> Dict:
#     """
#     Cancel a running scraping task
#     """
#     try:
#         task = AsyncResult(task_id, app=celery_app)
#         if task.state in ["PENDING", "STARTED"]:
#             celery_app.control.revoke(task_id, terminate=True)
#             return {"message": f"Task {task_id} has been cancelled"}
#         return {"message": f"Task {task_id} is already complete or doesn't exist"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


# ----------------------------------------


# @router.post("/scrape")
# def trigger_scraping():
#     """Trigger job scraping manually"""
#     try:
#         # Use the correct task name
#         task = celery_app.send_task("app.tasks.scraping_tasks.run_scraping_workflow")
#         return {
#             "message": "Job scraping started",
#             "task_id": task.id,
#             "status": "accepted",
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/scrape/status/{task_id}")
# async def get_scraping_status(task_id: str):
#     """Get status of a scraping task"""
#     task = celery_app.AsyncResult(task_id)
#     return {
#         "task_id": task_id,
#         "status": task.status,
#         "result": task.result if task.ready() else None,
#     }


# @router.post("/scrape", response_model=dict)
# async def trigger_scrape(
#     background_tasks: BackgroundTasks, db: Session = Depends(get_db)
# ):
#     """Trigger job scraping manually"""
#     try:
#         background_tasks.add_task(scrape_and_process_jobs)
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
