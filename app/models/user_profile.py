from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db.base import Base
from ..schemas.profile import UserProfileStatus


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Onboarding Details
    profile_status = Column(
        Enum(UserProfileStatus), default=UserProfileStatus.INCOMPLETE
    )

    # Personal Information
    current_role = Column(String(255))
    professional_title = Column(String(255))

    # Career Preferences
    career_stage = Column(String(100))  # Student, Working Professional, etc.
    domains = Column(String(500))  # Comma-separated domains of interest
    experience_level = Column(String(100))

    # Resume Details
    resume_file_path = Column(String(500))
    resume_uploaded_at = Column(DateTime(timezone=True))

    # Modify the relationship to resolve the cascade issue
    user = relationship(
        "User",
        back_populates="profile",
        # Remove delete-orphan from this side
        # Use single_parent to ensure unique relationship
        single_parent=True,
    )
