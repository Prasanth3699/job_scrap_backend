from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from ..db.base import Base
from datetime import datetime


class ScrapingHistory(Base):
    __tablename__ = "scraping_history"

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True), nullable=True)
    jobs_found = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, success, failed
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_start_time", start_time),
        Index("idx_status", status),
    )
