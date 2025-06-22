import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, timedelta
from sqlalchemy import desc, or_, and_, func
from typing import Any, Dict, List, Optional, Tuple

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

    def get_filtered_jobs(
        self,
        skip: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        search: Optional[str] = None,
        location: Optional[List[str]] = None,
        job_type: Optional[List[str]] = None,
        experience: Optional[List[str]] = None,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        date_from: Optional[date] = None,
    ) -> Tuple[List[Job], int]:
        """
        Get jobs with filters and return total count
        """
        try:
            query = self.db.query(Job)

            # Apply filters
            filters = []

            if search:
                search_filter = or_(
                    Job.job_title.ilike(f"%{search}%"),
                    Job.company_name.ilike(f"%{search}%"),
                    Job.description.ilike(f"%{search}%"),
                )
                filters.append(search_filter)

            if location:
                filters.append(Job.location.in_(location))

            if job_type:
                filters.append(Job.job_type.in_(job_type))

            if experience:
                filters.append(Job.experience.in_(experience))

            if date_from:
                filters.append(Job.posting_date >= date_from)

            # Apply all filters
            if filters:
                query = query.filter(and_(*filters))

            # Get total count before pagination
            total = query.count()

            # Apply pagination and ordering
            jobs = (
                query.order_by(desc(Job.posting_date)).offset(skip).limit(limit).all()
            )

            return jobs, total

        except Exception as e:
            error_msg = f"Error fetching filtered jobs: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_related_jobs(self, job: Job, limit: int = 3) -> List[Job]:
        """
        Get related jobs based on job title, type, and location
        """
        try:
            # Create a base query excluding the current job
            query = self.db.query(Job).filter(Job.id != job.id)

            # Split the job title into keywords
            keywords = job.job_title.lower().split()
            title_filters = [
                Job.job_title.ilike(f"%{keyword}%") for keyword in keywords
            ]

            # Combine filters with OR conditions
            related_filter = or_(
                *title_filters,
                Job.job_type == job.job_type,
                Job.location == job.location,
                Job.experience == job.experience,
            )

            # Apply filters and get results
            related_jobs = (
                query.filter(related_filter)
                .order_by(desc(Job.posting_date))
                .limit(limit)
                .all()
            )

            return related_jobs

        except Exception as e:
            error_msg = f"Error fetching related jobs: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_by_id(self, job_id: int) -> Optional[Job]:
        """Get job by ID"""
        try:
            return self.db.query(Job).filter(Job.id == job_id).first()
        except Exception as e:
            error_msg = f"Error fetching job by ID: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_by_url(self, detail_url: str) -> Optional[Job]:
        """Get job by URL"""
        try:
            return self.db.query(Job).filter(Job.detail_url == detail_url).first()
        except Exception as e:
            error_msg = f"Error fetching job by URL: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_jobs(
        self,
        skip: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        date_from: Optional[date] = None,
    ) -> List[Job]:
        """Get paginated jobs"""
        try:
            jobs, _ = self.get_filtered_jobs(
                skip=skip, limit=limit, date_from=date_from
            )
            return jobs
        except Exception as e:
            error_msg = f"Error fetching jobs: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_recent_jobs(self, days: int = 1) -> List[Job]:
        """Get recent jobs from the last N days"""
        try:
            date_from = date.today() - timedelta(days=days)
            return self.get_jobs(date_from=date_from)
        except Exception as e:
            error_msg = f"Error fetching recent jobs: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

    def get_job_stats(self) -> Dict[str, Any]:
        """Get job statistics"""
        try:
            stats = {
                "total_jobs": self.db.query(func.count(Job.id)).scalar(),
                "total_companies": self.db.query(
                    func.count(func.distinct(Job.company_name))
                ).scalar(),
                "job_types": self.db.query(Job.job_type, func.count(Job.id))
                .group_by(Job.job_type)
                .all(),
                "locations": self.db.query(Job.location, func.count(Job.id))
                .group_by(Job.location)
                .all(),
                "experience_levels": self.db.query(Job.experience, func.count(Job.id))
                .group_by(Job.experience)
                .all(),
            }
            return stats
        except Exception as e:
            error_msg = f"Error fetching job statistics: {str(e)}"
            logger.error(error_msg)
            raise DatabaseException(error_msg)

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
