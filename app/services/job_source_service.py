from sqlalchemy.orm import Session
from ..models.job_source import JobSource
from ..core.logger import logger
from typing import List, Optional, Dict, Any


class JobSourceService:
    @staticmethod
    def get_all_sources(db: Session) -> List[JobSource]:
        """Get all job sources regardless of status"""
        return db.query(JobSource).all()

    @staticmethod
    def get_active_sources(db: Session) -> List[JobSource]:
        """Get all active job sources"""
        return db.query(JobSource).filter(JobSource.is_active == True).all()

    @staticmethod
    def get_source_by_id(db: Session, source_id: int) -> Optional[JobSource]:
        """Get job source by ID"""
        return db.query(JobSource).filter(JobSource.id == source_id).first()

    @staticmethod
    def create_source(
        db: Session, name: str, url: str, config: Dict[str, Any] = None
    ) -> JobSource:
        """Create new job source"""
        source = JobSource(name=name, url=url, scraping_config=config or {})
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def update_source(
        db: Session, source_id: int, data: Dict[str, Any]
    ) -> Optional[JobSource]:
        """Update job source"""
        source = db.query(JobSource).filter(JobSource.id == source_id).first()
        if source:
            # Handle scraping_config separately
            if "scraping_config" in data and data["scraping_config"]:
                # If source doesn't have config, initialize it
                if not source.scraping_config:
                    source.scraping_config = {}

                # Update only the provided config values
                config_update = data["scraping_config"]
                if isinstance(config_update, dict):
                    source.scraping_config.update(config_update)

                # Remove scraping_config from data to prevent double processing
                data = {k: v for k, v in data.items() if k != "scraping_config"}

            # Update other fields
            for key, value in data.items():
                if hasattr(source, key):
                    setattr(source, key, value)

            try:
                db.commit()
                db.refresh(source)
                return source
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating source: {str(e)}")
                raise
        return None

    @staticmethod
    def delete_source(db: Session, source_id: int) -> bool:
        """Delete job source"""
        source = JobSourceService.get_source_by_id(db, source_id)
        if source:
            db.delete(source)
            db.commit()
            return True
        return False
