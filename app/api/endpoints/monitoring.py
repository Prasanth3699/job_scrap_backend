from fastapi import APIRouter, HTTPException
from typing import Dict, List

from ...core.celery_config import celery_app

router = APIRouter()


@router.get("/workers", response_model=Dict)
async def get_workers_status() -> Dict:
    """
    Get status of all Celery workers
    """
    try:
        inspect = celery_app.control.inspect()

        return {
            "active": inspect.active() or {},
            "reserved": inspect.reserved() or {},
            "registered": inspect.registered() or {},
            "scheduled": inspect.scheduled() or {},
            "active_queues": inspect.active_queues() or {},
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workers status: {str(e)}"
        )


@router.get("/tasks/active", response_model=Dict)
async def get_active_tasks() -> Dict:
    """
    Get all active tasks
    """
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        return {"active_tasks": active_tasks or {}}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get active tasks: {str(e)}"
        )
