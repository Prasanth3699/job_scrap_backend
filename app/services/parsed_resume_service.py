import os, uuid, shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import pytz

from typing import Any

from app.models.parsed_resume import ParsedResume
from app.models.user_profile import UserProfile, UserProfileStatus
from app.schemas.parsed_resume import ParsedResumeCreate

# Set timezone to IST (Indian Standard Time)
IST = pytz.timezone("Asia/Kolkata")


class ParsedResumeService:

    @staticmethod
    def save_file_and_data(
        db: Session,
        user_id: int,
        file: Any,  # starlette UploadFile OR file-like
        upload_directory: str,
        data: ParsedResumeCreate,
    ) -> ParsedResume:
        """
        1. Replace the official resume on disk and profile.resume_file_path
        2. Insert (or replace) a row in parsed_resumes for the same user
        """

        # ---------------------------------------------------------------
        # 1) ‑- save the FILE  (same logic you already had, + delete old)
        # ---------------------------------------------------------------
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)

        # delete previous file
        if profile.resume_file_path:
            try:
                old = Path(profile.resume_file_path)
                if old.exists():
                    old.unlink()
            except Exception:
                pass  # don’t fail on delete errors

        # write new file
        file_ext = file.filename.split(".")[-1]
        filename = f"{user_id}_{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(upload_directory, filename)
        os.makedirs(upload_directory, exist_ok=True)
        with open(file_path, "wb") as buff:
            shutil.copyfileobj(file.file, buff)

        profile.resume_file_path = file_path
        profile.resume_uploaded_at = datetime.now(IST)
        profile.profile_status = UserProfileStatus.COMPLETED
        db.add(profile)

        # ---------------------------------------------------------------
        # 2) ‑- upsert into parsed_resumes
        # ---------------------------------------------------------------
        # business decision: keep just ONE row per user (latest upload)
        pr = db.query(ParsedResume).filter(ParsedResume.user_id == user_id).first()
        if not pr:
            pr = ParsedResume(user_id=user_id)

        pr.resume_file_path = file_path
        pr.raw_text = data.raw_text
        pr.parsed_data = data.parsed_data
        pr.metadata = data.metadata
        pr.uploaded_at = datetime.now(IST)

        db.add(pr)
        db.commit()
        db.refresh(pr)

        return pr
