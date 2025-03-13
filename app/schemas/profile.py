from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum


class UserProfileStatus(str, Enum):
    INCOMPLETE = "incomplete"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserProfileCreate(BaseModel):
    career_stage: str
    current_role: Optional[str] = None
    professional_title: Optional[str] = None
    domains: Optional[List[str]] = None
    experience_level: Optional[str] = None

    @field_validator("domains", mode="before")
    @classmethod
    def convert_domains(cls, v):
        # If a string is passed, convert it to a list
        if isinstance(v, str):
            return [v.strip()]
        # If already a list, return as-is
        elif isinstance(v, list):
            return v
        # If None or empty, return empty list
        return []

    @field_validator("career_stage")
    @classmethod
    def validate_career_stage(cls, v):
        valid_stages = ["Student", "Working Professional", "Freelancer", "Job Seeker"]
        if v not in valid_stages:
            raise ValueError(f"Invalid career stage. Must be one of {valid_stages}")
        return v


class UserProfileResponse(BaseModel):
    id: Optional[int]
    user_id: int
    profile_status: UserProfileStatus
    current_role: Optional[str]
    professional_title: Optional[str]
    career_stage: Optional[str]
    domains: Optional[str]
    experience_level: Optional[str]
    resume_file_path: Optional[str]
    resume_uploaded_at: Optional[datetime]

    class Config:
        from_attributes = True
