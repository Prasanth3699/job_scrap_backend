# app/api/v1/endpoints/parsed_resume.py      (register it in main router)
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import json

from app.db.session import get_db
from app.services.parsed_resume_service import ParsedResumeService
from app.schemas.parsed_resume import ParsedResumeCreate, ParsedResumeResponse
from ...core.auth import get_current_user
from app.models.user import User
import os

router = APIRouter()
UPLOAD_DIRECTORY = os.path.join(os.getcwd(), "uploads")


@router.post(
    "/upload-parsed-resume",
    response_model=ParsedResumeResponse,
    status_code=201,
)
async def upload_parsed_resume(
    file: UploadFile = File(...),
    raw_text: str = File(...),  # <-- sent as form-field
    parsed_data: str = File(...),  # <-- JSON serialised string
    metadata: str = File(...),  # <-- JSON serialised string
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data_obj = ParsedResumeCreate(
            raw_text=raw_text,
            parsed_data=json.loads(parsed_data or "{}"),
            metadata=json.loads(metadata or "{}"),
        )

        result = ParsedResumeService.save_file_and_data(
            db=db,
            user_id=current_user.id,
            file=file,
            upload_directory=UPLOAD_DIRECTORY,
            data=data_obj,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
