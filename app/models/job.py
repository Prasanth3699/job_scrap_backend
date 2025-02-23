from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Index
from sqlalchemy.sql import func
from ..db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String(255), nullable=False)
    company_name = Column(String(255))
    job_type = Column(String(100))
    category = Column(String(100))
    salary = Column(String(100))
    experience = Column(String(100))
    location = Column(String(255))
    description = Column(Text)
    detail_url = Column(String(500), unique=True)
    apply_link = Column(String(500))
    posting_date = Column(Date, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Job {self.job_title}>"

    def __str__(self):
        return self.job_title

    __table_args__ = (
        Index("idx_job_title_company", job_title, company_name),
        Index("idx_posting_date", posting_date),
    )
