"""
Data retention and cleanup service for managing database storage.
Implements intelligent data lifecycle management for job scraper data.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, delete, and_, or_
from dataclasses import dataclass

from ..db.session import get_db
from ..models.job import Job
from ..models.user import User
from ..models.scraping_history import ScrapingHistory
from ..models.parsed_resume import ParsedResume
from ..core.logger import logger
from ..core.config import get_settings

settings = get_settings()


@dataclass
class RetentionPolicy:
    """Data retention policy configuration"""
    
    # Job data retention (in days)
    JOB_DATA_RETENTION_DAYS = int(os.getenv("JOB_DATA_RETENTION_DAYS", "90"))  # 3 months
    
    # Stale job removal (jobs not updated recently)
    STALE_JOB_DAYS = int(os.getenv("STALE_JOB_DAYS", "30"))  # 1 month
    
    # Scraping history retention
    SCRAPING_HISTORY_RETENTION_DAYS = int(os.getenv("SCRAPING_HISTORY_RETENTION_DAYS", "30"))
    
    # Resume data retention (keep longer for user data)
    RESUME_DATA_RETENTION_DAYS = int(os.getenv("RESUME_DATA_RETENTION_DAYS", "365"))  # 1 year
    
    # Inactive user data cleanup
    INACTIVE_USER_DAYS = int(os.getenv("INACTIVE_USER_DAYS", "730"))  # 2 years
    
    # Log file retention
    LOG_FILE_RETENTION_DAYS = int(os.getenv("LOG_FILE_RETENTION_DAYS", "30"))
    
    # Batch size for cleanup operations
    CLEANUP_BATCH_SIZE = int(os.getenv("CLEANUP_BATCH_SIZE", "1000"))


@dataclass
class CleanupResult:
    """Result of cleanup operation"""
    total_processed: int
    total_deleted: int
    space_freed_mb: float
    duration_seconds: float
    errors: List[str]


class DataRetentionService:
    """Service for managing data retention and cleanup"""
    
    def __init__(self):
        self.policy = RetentionPolicy()
        
    def cleanup_old_jobs(self, db: Session) -> CleanupResult:
        """
        Clean up old job data based on retention policy.
        Removes jobs older than retention period.
        """
        start_time = datetime.now()
        errors = []
        total_deleted = 0
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=self.policy.JOB_DATA_RETENTION_DAYS
            )
            
            logger.info(f"Starting job cleanup for jobs older than {cutoff_date}")
            
            # Get count of jobs to be deleted
            jobs_to_delete = db.query(Job).filter(
                Job.created_at < cutoff_date
            ).count()
            
            if jobs_to_delete == 0:
                logger.info("No old jobs found for cleanup")
                return CleanupResult(
                    total_processed=0,
                    total_deleted=0,
                    space_freed_mb=0.0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[]
                )
            
            # Estimate space before deletion (rough estimate)
            space_before = self._estimate_table_size(db, "jobs")
            
            # Delete in batches to avoid long-running transactions
            batch_size = self.policy.CLEANUP_BATCH_SIZE
            total_processed = 0
            
            while True:
                # Get batch of job IDs to delete
                job_ids = db.query(Job.id).filter(
                    Job.created_at < cutoff_date
                ).limit(batch_size).all()
                
                if not job_ids:
                    break
                
                job_ids = [job_id[0] for job_id in job_ids]
                
                try:
                    # Delete batch
                    result = db.execute(
                        delete(Job).where(Job.id.in_(job_ids))
                    )
                    
                    deleted_count = result.rowcount
                    total_deleted += deleted_count
                    total_processed += len(job_ids)
                    
                    db.commit()
                    
                    logger.info(f"Deleted batch of {deleted_count} jobs")
                    
                except Exception as e:
                    db.rollback()
                    error_msg = f"Error deleting job batch: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    break
                
                # Safety check to prevent infinite loops
                if total_processed >= jobs_to_delete * 2:
                    break
            
            # Estimate space freed
            space_after = self._estimate_table_size(db, "jobs")
            space_freed_mb = max(0.0, space_before - space_after)
            
            # Update table statistics
            db.execute("ANALYZE jobs")
            db.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Job cleanup completed: {total_deleted} jobs deleted, "
                f"{space_freed_mb:.2f}MB freed, took {duration:.2f}s"
            )
            
            return CleanupResult(
                total_processed=total_processed,
                total_deleted=total_deleted,
                space_freed_mb=space_freed_mb,
                duration_seconds=duration,
                errors=errors
            )
            
        except Exception as e:
            db.rollback()
            error_msg = f"Job cleanup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return CleanupResult(
                total_processed=0,
                total_deleted=0,
                space_freed_mb=0.0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=errors
            )
    
    def cleanup_stale_jobs(self, db: Session) -> CleanupResult:
        """
        Remove stale job entries (jobs that haven't been updated recently
        and are likely no longer available).
        """
        start_time = datetime.now()
        errors = []
        
        try:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(
                days=self.policy.STALE_JOB_DAYS
            )
            
            # Keep recent jobs and jobs that were recently updated
            jobs_to_delete = db.query(Job).filter(
                and_(
                    Job.updated_at < stale_cutoff,
                    Job.created_at < stale_cutoff,
                    # Additional criteria for stale jobs
                    or_(
                        Job.apply_link.like('%expired%'),
                        Job.apply_link.like('%not-found%'),
                        Job.description.like('%position filled%')
                    )
                )
            )
            
            total_stale = jobs_to_delete.count()
            logger.info(f"Found {total_stale} stale jobs to remove")
            
            if total_stale == 0:
                return CleanupResult(
                    total_processed=0,
                    total_deleted=0,
                    space_freed_mb=0.0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[]
                )
            
            # Delete stale jobs
            space_before = self._estimate_table_size(db, "jobs")
            deleted_count = jobs_to_delete.delete(synchronize_session=False)
            db.commit()
            space_after = self._estimate_table_size(db, "jobs")
            
            space_freed = max(0.0, space_before - space_after)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Removed {deleted_count} stale jobs in {duration:.2f}s")
            
            return CleanupResult(
                total_processed=total_stale,
                total_deleted=deleted_count,
                space_freed_mb=space_freed,
                duration_seconds=duration,
                errors=errors
            )
            
        except Exception as e:
            db.rollback()
            error_msg = f"Stale job cleanup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return CleanupResult(
                total_processed=0,
                total_deleted=0,
                space_freed_mb=0.0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[error_msg]
            )
    
    def cleanup_scraping_history(self, db: Session) -> CleanupResult:
        """Clean up old scraping history records"""
        start_time = datetime.now()
        errors = []
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=self.policy.SCRAPING_HISTORY_RETENTION_DAYS
            )
            
            history_to_delete = db.query(ScrapingHistory).filter(
                ScrapingHistory.created_at < cutoff_date
            )
            
            total_records = history_to_delete.count()
            
            if total_records == 0:
                return CleanupResult(
                    total_processed=0,
                    total_deleted=0,
                    space_freed_mb=0.0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[]
                )
            
            space_before = self._estimate_table_size(db, "scraping_history")
            deleted_count = history_to_delete.delete(synchronize_session=False)
            db.commit()
            space_after = self._estimate_table_size(db, "scraping_history")
            
            space_freed = max(0.0, space_before - space_after)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Cleaned up {deleted_count} scraping history records")
            
            return CleanupResult(
                total_processed=total_records,
                total_deleted=deleted_count,
                space_freed_mb=space_freed,
                duration_seconds=duration,
                errors=errors
            )
            
        except Exception as e:
            db.rollback()
            error_msg = f"Scraping history cleanup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return CleanupResult(
                total_processed=0,
                total_deleted=0,
                space_freed_mb=0.0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[error_msg]
            )
    
    def cleanup_old_resume_data(self, db: Session) -> CleanupResult:
        """Clean up old parsed resume data"""
        start_time = datetime.now()
        errors = []
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=self.policy.RESUME_DATA_RETENTION_DAYS
            )
            
            # Only delete resume data for inactive users or very old data
            resumes_to_delete = db.query(ParsedResume).join(User).filter(
                and_(
                    ParsedResume.created_at < cutoff_date,
                    or_(
                        User.is_active == False,
                        User.last_login < cutoff_date
                    )
                )
            )
            
            total_resumes = resumes_to_delete.count()
            
            if total_resumes == 0:
                return CleanupResult(
                    total_processed=0,
                    total_deleted=0,
                    space_freed_mb=0.0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[]
                )
            
            # Also clean up associated files
            resume_files_deleted = 0
            for resume in resumes_to_delete:
                if resume.file_path and os.path.exists(resume.file_path):
                    try:
                        os.remove(resume.file_path)
                        resume_files_deleted += 1
                    except Exception as e:
                        errors.append(f"Failed to delete resume file {resume.file_path}: {str(e)}")
            
            deleted_count = resumes_to_delete.delete(synchronize_session=False)
            db.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Cleaned up {deleted_count} old resume records and "
                f"{resume_files_deleted} files"
            )
            
            return CleanupResult(
                total_processed=total_resumes,
                total_deleted=deleted_count,
                space_freed_mb=resume_files_deleted * 0.5,  # Rough estimate
                duration_seconds=duration,
                errors=errors
            )
            
        except Exception as e:
            db.rollback()
            error_msg = f"Resume data cleanup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return CleanupResult(
                total_processed=0,
                total_deleted=0,
                space_freed_mb=0.0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[error_msg]
            )
    
    def cleanup_log_files(self) -> CleanupResult:
        """Clean up old log files"""
        start_time = datetime.now()
        errors = []
        total_deleted = 0
        space_freed = 0.0
        
        try:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "core", "logs")
            
            if not os.path.exists(log_dir):
                logger.info("Log directory does not exist, skipping log cleanup")
                return CleanupResult(
                    total_processed=0,
                    total_deleted=0,
                    space_freed_mb=0.0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[]
                )
            
            cutoff_date = datetime.now() - timedelta(
                days=self.policy.LOG_FILE_RETENTION_DAYS
            )
            
            for filename in os.listdir(log_dir):
                file_path = os.path.join(log_dir, filename)
                
                if not os.path.isfile(file_path):
                    continue
                
                # Skip current log files
                if filename in ["app.log", "error.log"]:
                    continue
                
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_date:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        
                        total_deleted += 1
                        space_freed += file_size / (1024 * 1024)  # Convert to MB
                        
                        logger.debug(f"Deleted old log file: {filename}")
                        
                except Exception as e:
                    error_msg = f"Failed to delete log file {filename}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Log cleanup completed: {total_deleted} files deleted, "
                f"{space_freed:.2f}MB freed"
            )
            
            return CleanupResult(
                total_processed=total_deleted,
                total_deleted=total_deleted,
                space_freed_mb=space_freed,
                duration_seconds=duration,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Log file cleanup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return CleanupResult(
                total_processed=0,
                total_deleted=0,
                space_freed_mb=0.0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[error_msg]
            )
    
    def run_full_cleanup(self, db: Session) -> Dict[str, CleanupResult]:
        """Run all cleanup operations"""
        logger.info("Starting full data retention cleanup")
        
        results = {}
        
        # Job data cleanup
        results["old_jobs"] = self.cleanup_old_jobs(db)
        results["stale_jobs"] = self.cleanup_stale_jobs(db)
        
        # History cleanup
        results["scraping_history"] = self.cleanup_scraping_history(db)
        
        # Resume data cleanup
        results["resume_data"] = self.cleanup_old_resume_data(db)
        
        # Log file cleanup
        results["log_files"] = self.cleanup_log_files()
        
        # Summary
        total_deleted = sum(result.total_deleted for result in results.values())
        total_space_freed = sum(result.space_freed_mb for result in results.values())
        total_errors = sum(len(result.errors) for result in results.values())
        
        logger.info(
            f"Full cleanup completed: {total_deleted} records deleted, "
            f"{total_space_freed:.2f}MB freed, {total_errors} errors"
        )
        
        return results
    
    def get_retention_stats(self, db: Session) -> Dict[str, any]:
        """Get statistics about data retention"""
        try:
            stats = {}
            
            # Job statistics
            total_jobs = db.query(func.count(Job.id)).scalar()
            old_jobs = db.query(func.count(Job.id)).filter(
                Job.created_at < datetime.now(timezone.utc) - timedelta(
                    days=self.policy.JOB_DATA_RETENTION_DAYS
                )
            ).scalar()
            
            stats["jobs"] = {
                "total": total_jobs,
                "eligible_for_cleanup": old_jobs,
                "retention_days": self.policy.JOB_DATA_RETENTION_DAYS
            }
            
            # Scraping history statistics
            total_history = db.query(func.count(ScrapingHistory.id)).scalar()
            old_history = db.query(func.count(ScrapingHistory.id)).filter(
                ScrapingHistory.created_at < datetime.now(timezone.utc) - timedelta(
                    days=self.policy.SCRAPING_HISTORY_RETENTION_DAYS
                )
            ).scalar()
            
            stats["scraping_history"] = {
                "total": total_history,
                "eligible_for_cleanup": old_history,
                "retention_days": self.policy.SCRAPING_HISTORY_RETENTION_DAYS
            }
            
            # Database size estimation
            stats["database_size"] = {
                "jobs_table_mb": self._estimate_table_size(db, "jobs"),
                "scraping_history_table_mb": self._estimate_table_size(db, "scraping_history"),
                "parsed_resume_table_mb": self._estimate_table_size(db, "parsed_resume")
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting retention stats: {str(e)}")
            return {"error": str(e)}
    
    def _estimate_table_size(self, db: Session, table_name: str) -> float:
        """Estimate table size in MB (PostgreSQL specific)"""
        try:
            result = db.execute(
                f"SELECT pg_total_relation_size('{table_name}') / (1024.0 * 1024.0) as size_mb"
            ).fetchone()
            return float(result[0]) if result else 0.0
        except Exception:
            return 0.0


# Global instance
data_retention_service = DataRetentionService()


# Scheduler integration
def schedule_cleanup_jobs():
    """Schedule regular cleanup jobs"""
    try:
        db = next(get_db())
        results = data_retention_service.run_full_cleanup(db)
        
        # Log summary
        total_deleted = sum(result.total_deleted for result in results.values())
        logger.info(f"Scheduled cleanup completed: {total_deleted} records deleted")
        
        return results
        
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {str(e)}")
        return {"error": str(e)}