from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...services.settings_service import SettingsService
from ...services.scheduler_service import update_scheduler
from typing import Dict, Any

router = APIRouter()


@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    settings = SettingsService.get_settings(db)
    return {
        "email_config": settings.email_config,
        "scheduler_config": settings.scheduler_config,
        "selenium_config": settings.selenium_config,
    }


@router.put("")
async def update_settings(settings_data: Dict[str, Any], db: Session = Depends(get_db)):
    settings = SettingsService.update_settings(db, settings_data)
    # Update scheduler if scheduler settings changed
    if "scheduler_config" in settings_data:
        update_scheduler()
    return settings


@router.put("/email")
async def update_email_settings(email_config: dict, db: Session = Depends(get_db)):
    try:
        settings = SettingsService.update_settings(db, {"email_config": email_config})
        return {
            "message": "Email settings updated successfully",
            "config": settings.email_config,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings/email")
def get_email_settings(db: Session = Depends(get_db)):
    return SettingsService.get_email_config(db)


@router.get("/scheduler")
def get_scheduler_settings(db: Session = Depends(get_db)):
    return SettingsService.get_scheduler_config(db)


@router.put("/scheduler")
async def update_scheduler_settings(
    scheduler_config: dict, db: Session = Depends(get_db)
):
    try:
        settings = SettingsService.update_settings(
            db, {"scheduler_config": scheduler_config}
        )
        update_scheduler()  # Update the scheduler with new settings
        return {
            "message": "Scheduler settings updated successfully",
            "config": settings.scheduler_config,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings/selenium")
def get_selenium_settings(db: Session = Depends(get_db)):
    return SettingsService.get_selenium_config(db)
