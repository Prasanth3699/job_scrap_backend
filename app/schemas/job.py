from pydantic import BaseModel, HttpUrl
from datetime import date, datetime
from typing import Optional


class JobBase(BaseModel):
    job_title: str
    company_name: Optional[str] = None
    job_type: Optional[str] = None
    salary: Optional[str] = None
    experience: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    detail_url: HttpUrl
    apply_link: HttpUrl
    posting_date: date


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobUpdate(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_type: Optional[str] = None
    salary: Optional[str] = None
    experience: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    apply_link: Optional[HttpUrl] = None
