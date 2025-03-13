from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    is_admin: bool = False


class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    admin_secret_key: str  # For admin registration validation


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool
    is_admin: Optional[bool] = False

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserProfileCreate(BaseModel):
    career_stage: str
    current_role: Optional[str] = None
    professional_title: Optional[str] = None
    domains: Optional[str] = None
    experience_level: Optional[str] = None


class ResumeUploadSchema(BaseModel):
    file_path: str
    uploaded_at: datetime  # Use datetime.datetime if you import the module


class UserProfileResponse(BaseModel):
    career_stage: str
    current_role: Optional[str]
    professional_title: Optional[str]
    domains: Optional[str]
    experience_level: Optional[str]
    resume_uploaded: bool

    class Config:
        from_attributes = True
