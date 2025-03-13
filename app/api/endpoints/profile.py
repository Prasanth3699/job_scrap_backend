from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import os

from app.db.session import get_db
from ...core.auth import get_current_user
from app.models.user import User
from app.schemas.profile import UserProfileCreate, UserProfileResponse
from app.services.profile_service import ProfileService

# Define upload directory
UPLOAD_DIRECTORY = os.path.join(os.getcwd(), "uploads")

# Create the directory if it doesn't exist
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

router = APIRouter()


@router.post("/onboarding", response_model=UserProfileResponse)
async def create_profile(
    profile_data: UserProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Validate user
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Create or update profile
        profile = ProfileService.create_or_update_profile(
            db, current_user.id, profile_data
        )
        return profile
    except Exception as e:
        # Log the error for debugging
        print(f"Profile creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Validate user
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Validate file type and size
        allowed_extensions = {".pdf", ".doc", ".docx"}
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF and Word documents are allowed.",
            )

        # Optional: Check file size (e.g., max 5MB)
        file.file.seek(0, 2)  # Move to end of file
        file_size = file.file.tell()
        file.file.seek(0)  # Reset file pointer

        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size exceeds 5MB limit.")

        # Upload resume
        profile = ProfileService.upload_resume(
            db, current_user.id, file, UPLOAD_DIRECTORY
        )

        return {"message": "Resume uploaded successfully", "profile": profile}
    except Exception as e:
        # Log the error for debugging
        print(f"Resume upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        # Validate user
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        profile = ProfileService.get_user_profile(db, current_user.id)
        return profile
    except Exception as e:
        # Log the error for debugging
        print(f"Get profile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
