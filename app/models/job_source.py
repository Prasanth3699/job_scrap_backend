from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..db.base import Base


class JobSource(Base):
    __tablename__ = "job_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    is_active = Column(Boolean, default=True)
    scraping_config = Column(JSON, nullable=True)
    last_scraped_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship with ScrapingHistory
    scraping_histories = relationship("ScrapingHistory", back_populates="source")
