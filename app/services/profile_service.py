from typing import Any
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import os
import shutil

from app.models.user import User
from app.models.profile import UserProfile, UserProfileStatus
from app.schemas.profile import UserProfileCreate


class ProfileService:
    @staticmethod
    def create_or_update_profile(
        db: Session, user_id: int, profile_data: UserProfileCreate
    ) -> UserProfile:
        try:
            # Check if profile exists
            profile = (
                db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            )

            if not profile:
                # Create new profile
                profile = UserProfile(user_id=user_id)

            # Update profile fields
            profile.career_stage = profile_data.career_stage
            profile.current_role = profile_data.current_role
            profile.professional_title = profile_data.professional_title
            profile.domains = (
                ",".join(profile_data.domains) if profile_data.domains else None
            )
            profile.experience_level = profile_data.experience_level

            # Update profile status
            profile.profile_status = UserProfileStatus.IN_PROGRESS

            db.add(profile)
            db.commit()
            db.refresh(profile)

            return profile
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def upload_resume(
        db: Session,
        user_id: int,
        file: Any,  # Use appropriate type for file
        upload_directory: str,
    ) -> UserProfile:
        try:
            # Find user profile
            profile = (
                db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            )

            if not profile:
                # Create profile if not exists
                profile = UserProfile(user_id=user_id)

            # Generate unique filename
            file_extension = file.filename.split(".")[-1]
            filename = f"{user_id}_{uuid.uuid4()}.{file_extension}"

            # Save file to storage
            file_path = os.path.join(upload_directory, filename)

            # Ensure directory exists
            os.makedirs(upload_directory, exist_ok=True)

            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Update resume details
            profile.resume_file_path = file_path
            profile.resume_uploaded_at = datetime.now()
            profile.profile_status = UserProfileStatus.COMPLETED

            db.add(profile)
            db.commit()
            db.refresh(profile)

            return profile
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def get_user_profile(db: Session, user_id: int) -> UserProfile:
        try:
            profile = (
                db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            )

            if not profile:
                # Create empty profile if not exists
                profile = UserProfile(
                    user_id=user_id, profile_status=UserProfileStatus.INCOMPLETE
                )
                db.add(profile)
                db.commit()
                db.refresh(profile)

            return profile
        except Exception as e:
            raise
