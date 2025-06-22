from fastapi import APIRouter, Depends, HTTPException, Body
from loguru import logger
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...services.job_source_service import JobSourceService
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()


# Pydantic models for request/response
class ScrapingConfig(BaseModel):
    max_jobs: Optional[int] = None
    scroll_pause_time: Optional[float] = None
    element_timeout: Optional[int] = None


class JobSourceCreate(BaseModel):
    name: str
    url: str
    scraping_config: Optional[ScrapingConfig] = None


class JobSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    scraping_config: Optional[ScrapingConfig] = None


@router.get("")
def get_sources(db: Session = Depends(get_db)):
    """Get all active job sources"""
    return JobSourceService.get_all_sources(db)


@router.post("")
def create_source(
    source: JobSourceCreate = Body(...),
    db: Session = Depends(get_db),
):
    """Create a new job source"""
    try:
        return JobSourceService.create_source(
            db=db, name=source.name, url=source.url, config=source.config
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{source_id}")
def update_source(
    source_id: int, source: JobSourceUpdate = Body(...), db: Session = Depends(get_db)
):
    """Update an existing job source"""
    try:
        # Convert the Pydantic model to dict, keeping nested structures
        update_data = source.dict(exclude_unset=True, exclude_none=True)

        # If scraping_config is present, ensure it's properly formatted
        if "scraping_config" in update_data:
            scraping_config = update_data["scraping_config"]
            if isinstance(scraping_config, dict):
                # Remove None values from scraping_config
                update_data["scraping_config"] = {
                    k: v for k, v in scraping_config.items() if v is not None
                }

        updated_source = JobSourceService.update_source(
            db=db, source_id=source_id, data=update_data
        )

        if not updated_source:
            raise HTTPException(status_code=404, detail="Source not found")

        return updated_source

    except Exception as e:
        logger.error(f"Error updating source {source_id}: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Failed to update source: {str(e)}"
        )


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a job source"""
    if not JobSourceService.delete_source(db, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return {"message": "Source deleted successfully"}
