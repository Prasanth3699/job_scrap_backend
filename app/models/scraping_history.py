from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Index
from ..db.base import Base
from sqlalchemy.orm import relationship


class ScrapingHistory(Base):
    __tablename__ = "scraping_history"

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True), nullable=True)
    jobs_found = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, success, failed
    error = Column(Text, nullable=True)
    jobs_found = Column(Integer, default=0)
    source_id = Column(Integer, ForeignKey("job_sources.id", ondelete="SET NULL"))

    # Add relationship to JobSource
    source = relationship("JobSource", back_populates="scraping_histories")

    __table_args__ = (
        Index("idx_start_time", start_time),
        Index("idx_status", status),
    )
