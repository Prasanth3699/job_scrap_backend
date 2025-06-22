from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.sql import func
from ..db.base import Base


class ParsedResume(Base):
    __tablename__ = "parsed_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # full path of the file we saved (same value as profile.resume_file_path)
    resume_file_path = Column(String(500))
    # text produced by your parser
    raw_text = Column(Text)
    # Anything that can be serialised as JSON (skills, education, …)
    parsed_data = Column(JSON)
    # Optional extra metadata coming from the parser (dict/JSON)
    metadata_ = Column("metadata", JSON)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
