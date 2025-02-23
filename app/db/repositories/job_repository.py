import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ...utils.exceptions import DatabaseException
from ...models.job import Job
from ...schemas.job import JobCreate, JobUpdate
from ...core.constants import DEFAULT_LIMIT, DEFAULT_OFFSET
from app.core.logger import logger


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    async def store_jobs(self, jobs: List[Dict[str, Any]]) -> List[Job]:
        """Store multiple jobs in the database"""
        try:
            logger.info(f"Attempting to store {len(jobs)} jobs")
            new_jobs = []
            for job_data in jobs:
                try:
                    # Convert posting_date string to date object using datetime.strptime
                    posting_date = datetime.datetime.strptime(
                        job_data["posting_date"], "%d %B %Y"
                    ).date()

                    job = Job(
                        job_title=job_data["job_title"],
                        posting_date=posting_date,
                        job_type=job_data.get("job_type", "N/A"),
                        salary=job_data.get("salary", "N/A"),
                        experience=job_data.get("experience", "N/A"),
                        detail_url=job_data["detail_url"],
                        apply_link=job_data["apply_link"],
                        company_name=job_data.get("company_name"),
                        location=job_data.get("location"),
                        description=job_data.get("description"),
                    )
                    new_jobs.append(job)
                    logger.info(f"Prepared job for storage: {job.job_title}")
                except Exception as e:
                    logger.error(f"Error preparing job for storage: {str(e)}")
                    continue

            if new_jobs:
                self.db.bulk_save_objects(new_jobs)
                self.db.commit()
                logger.info(f"Successfully stored {len(new_jobs)} jobs")
                return new_jobs
            return []

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error storing jobs: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_by_id(self, job_id: int) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == job_id).first()

    def get_by_url(self, detail_url: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.detail_url == detail_url).first()

    def get_jobs(
        self,
        skip: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        date_from: Optional[date] = None,
    ) -> List[Job]:
        query = self.db.query(Job)
        if date_from:
            query = query.filter(Job.posting_date >= date_from)
        return query.order_by(desc(Job.posting_date)).offset(skip).limit(limit).all()

    def get_recent_jobs(self, days: int = 1) -> List[Job]:
        date_from = date.today() - timedelta(days=days)
        return self.get_jobs(date_from=date_from)

    def update(self, job_id: int, job_data: Dict[str, Any]) -> Optional[Job]:
        """Update a job entry"""
        try:
            db_job = self.get_by_id(job_id)
            if db_job:
                for key, value in job_data.items():
                    if hasattr(db_job, key):
                        setattr(db_job, key, value)
                self.db.commit()
                self.db.refresh(db_job)
            return db_job
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Error updating job: {str(e)}")

    def delete(self, job_id: int) -> bool:
        """Delete a job entry"""
        try:
            db_job = self.get_by_id(job_id)
            if db_job:
                self.db.delete(db_job)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            raise DatabaseException(f"Error deleting job: {str(e)}")
