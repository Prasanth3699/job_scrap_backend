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
from ...core.auth import get_current_user
from ...models.user import User
from loguru import logger
from app.core.redis_lock import redis_lock_manager
from app.core.cache import JobCache, InternalCache
from app.services.event_publisher import get_event_publisher


router = APIRouter()


@router.post("/scrape", response_model=Dict[str, str])
async def trigger_scrape(
    source_id: Optional[int] = None,
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Only admin users can trigger scraping jobs"
        )
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
    current_user: User = Depends(get_current_user),
):
    """Get jobs with filters and pagination"""
    try:
        # Create cache key from search parameters
        search_params = {
            "page": page,
            "limit": limit,
            "search": search,
            "location": location,
            "job_type": job_type,
            "experience": experience,
            "salary_min": salary_min,
            "salary_max": salary_max,
        }

        # Try to get from cache first
        cached_result = JobCache.get_job_search(search_params)
        if cached_result:
            try:
                cached_result["jobs"] = [
                    JobResponse(**job) for job in cached_result["jobs"]
                ]

                return JobsResponse(**cached_result)
            except Exception as e:
                logger.error(f"Error decoding cached job data: {str(e)}")

        repo = JobRepository(db)
        skip = (page - 1) * limit

        # Get filtered jobs
        jobs, total = repo.get_filtered_jobs(
            skip=skip,
            limit=limit + 1,
            search=search,
            location=location,
            job_type=job_type,
            experience=experience,
            salary_min=salary_min,
            salary_max=salary_max,
        )

        # Check if there are more results
        has_more = len(jobs) > limit
        jobs = jobs[:limit]

        # Convert to JobResponse and serialize
        job_models = [JobResponse.model_validate(job) for job in jobs]
        serialized_jobs = [job.model_dump() for job in job_models]

        result = {
            "jobs": serialized_jobs,
            "total": total,
            "hasMore": has_more,
        }

        # Cache the result
        JobCache.set_job_search(search_params, result, ttl=300)

        return JobsResponse(jobs=job_models, total=total, hasMore=has_more)

    except Exception as e:
        logger.error(f"Error getting jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=List[JobResponse])
async def get_jobs_dashboard(
    db: Session = Depends(get_db),
    skip: int = Query(DEFAULT_OFFSET, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get scraped jobs"""
    try:
        repo = JobRepository(db)
        return repo.get_jobs(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent", response_model=List[JobResponse])
async def get_recent_jobs(
    db: Session = Depends(get_db),
    days: int = Query(1, ge=1, le=30),
    current_user: User = Depends(get_current_user),
):
    """Get recent jobs from the last N days"""
    try:
        repo = JobRepository(db)
        return repo.get_recent_jobs(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific job by ID"""
    repo = JobRepository(db)
    job = repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# DEPRECATED: This endpoint is being replaced by RabbitMQ event-driven architecture
# ML services should now send job data requests via message broker instead of direct API calls
@router.post("/ml/request-job-data")
async def request_job_data_for_ml(
    request_data: dict,
    current_user: User = Depends(get_current_user),
):
    """
    Trigger job data request to be sent via RabbitMQ to ML service.
    
    DEPRECATED: This is a transitional endpoint. ML services should directly 
    send events to RabbitMQ instead of using HTTP API calls.
    
    Expected request_data format:
    {
        "job_id": int,
        "ml_service_id": str,
        "request_id": str (optional),
        "additional_fields": List[str] (optional)
    }
    """
    try:
        from ...core.message_broker import EventType, EventMessage, message_broker
        from uuid import uuid4
        from datetime import datetime
        
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403, 
                detail="Only admin users can trigger ML data requests"
            )
        
        job_id = request_data.get("job_id")
        ml_service_id = request_data.get("ml_service_id", "ml-service")
        request_id = request_data.get("request_id", str(uuid4()))
        additional_fields = request_data.get("additional_fields", [])
        
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")
        
        # Create and send event message
        event_message = EventMessage(
            event_id=str(uuid4()),
            event_type=EventType.JOB_DATA_REQUESTED,
            source_service="core-service-api",
            timestamp=datetime.now().isoformat(),
            data={
                "job_id": job_id,
                "ml_service_id": ml_service_id,
                "request_id": request_id,
                "additional_fields": additional_fields
            }
        )
        
        # Publish event to message broker
        await message_broker.publish_message(
            event_message,
            routing_key=f"ml.job_data_requested"
        )
        
        logger.info(f"Job data request sent via RabbitMQ for job_id: {job_id}")
        
        return {
            "status": "success",
            "message": "Job data request sent via RabbitMQ",
            "request_id": request_id,
            "job_id": job_id,
            "ml_service_id": ml_service_id
        }
        
    except Exception as e:
        logger.error(f"Error sending job data request via RabbitMQ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send request: {str(e)}")


@router.post("/ml/request-bulk-job-data")
async def request_bulk_job_data_for_ml(
    request_data: dict,
    current_user: User = Depends(get_current_user),
):
    """
    Trigger bulk job data request to be sent via RabbitMQ to ML service.
    
    DEPRECATED: This is a transitional endpoint. ML services should directly 
    send events to RabbitMQ instead of using HTTP API calls.
    
    Expected request_data format:
    {
        "ml_service_id": str,
        "request_id": str (optional),
        "filters": {
            "job_ids": List[int] (optional),
            "limit": int (optional, default 100),
            "offset": int (optional, default 0),
            "location": List[str] (optional),
            "job_type": List[str] (optional),
            "experience": List[str] (optional),
            "date_from": str (optional),
            "date_to": str (optional)
        },
        "additional_fields": List[str] (optional)
    }
    """
    try:
        from ...core.message_broker import EventType, EventMessage, message_broker
        from uuid import uuid4
        from datetime import datetime
        
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403, 
                detail="Only admin users can trigger ML bulk data requests"
            )
        
        ml_service_id = request_data.get("ml_service_id", "ml-service")
        request_id = request_data.get("request_id", str(uuid4()))
        filters = request_data.get("filters", {})
        additional_fields = request_data.get("additional_fields", [])
        
        # Create and send event message
        event_message = EventMessage(
            event_id=str(uuid4()),
            event_type=EventType.BULK_JOB_DATA_REQUESTED,
            source_service="core-service-api",
            timestamp=datetime.now().isoformat(),
            data={
                "ml_service_id": ml_service_id,
                "request_id": request_id,
                "filters": filters,
                "additional_fields": additional_fields
            }
        )
        
        # Publish event to message broker
        await message_broker.publish_message(
            event_message,
            routing_key=f"ml.bulk_job_data_requested"
        )
        
        logger.info(f"Bulk job data request sent via RabbitMQ for ML service: {ml_service_id}")
        
        return {
            "status": "success",
            "message": "Bulk job data request sent via RabbitMQ",
            "request_id": request_id,
            "ml_service_id": ml_service_id,
            "filters": filters
        }
        
    except Exception as e:
        logger.error(f"Error sending bulk job data request via RabbitMQ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send request: {str(e)}")


@router.get("/{job_id}/related", response_model=List[JobResponse])
async def get_related_jobs(
    job_id: int,
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get related jobs based on current job"""
    repo = JobRepository(db)
    current_job = repo.get_by_id(job_id)
    if not current_job:
        raise HTTPException(status_code=404, detail="Job not found")

    related_jobs = repo.get_related_jobs(current_job, limit)
    return related_jobs
