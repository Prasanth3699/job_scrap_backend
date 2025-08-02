"""
Event publisher service for triggering events in the job scraper system.
Integrates with existing services to publish events to RabbitMQ.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from ..core.message_broker import get_message_broker, EventType, EventMessage
from ..core.logger import logger
from ..models.job import Job
from ..models.user import User


class EventPublisher:
    """Service for publishing domain events"""
    
    def __init__(self, service_name: str = "core-service"):
        self.service_name = service_name
        self.message_broker = get_message_broker(service_name)
    
    # Job-related events
    async def publish_job_scraped(self, job: Job, scraping_source: str = "unknown"):
        """Publish event when a new job is scraped"""
        try:
            event_data = {
                "job_id": job.id,
                "job_title": job.job_title,
                "company_name": job.company_name,
                "location": job.location,
                "job_type": job.job_type,
                "experience": job.experience,
                "salary": job.salary,
                "detail_url": job.detail_url,
                "apply_link": job.apply_link,
                "posting_date": job.posting_date.isoformat() if job.posting_date else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "scraping_source": scraping_source,
                "description_preview": job.description[:200] if job.description else None
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.JOB_SCRAPED,
                data=event_data
            )
            
            logger.info(f"Published job scraped event for job {job.id}: {job.job_title}")
            
        except Exception as e:
            logger.error(f"Failed to publish job scraped event for job {job.id}: {str(e)}")
    
    async def publish_jobs_bulk_imported(self, job_count: int, source: str, summary: Dict[str, Any]):
        """Publish event when multiple jobs are imported"""
        try:
            event_data = {
                "job_count": job_count,
                "source": source,
                "import_summary": summary,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.JOBS_BULK_IMPORTED,
                data=event_data
            )
            
            logger.info(f"Published bulk import event: {job_count} jobs from {source}")
            
        except Exception as e:
            logger.error(f"Failed to publish bulk import event: {str(e)}")
    
    async def publish_job_updated(self, job: Job, updated_fields: List[str]):
        """Publish event when a job is updated"""
        try:
            event_data = {
                "job_id": job.id,
                "job_title": job.job_title,
                "company_name": job.company_name,
                "updated_fields": updated_fields,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.JOB_UPDATED,
                data=event_data
            )
            
            logger.info(f"Published job updated event for job {job.id}")
            
        except Exception as e:
            logger.error(f"Failed to publish job updated event: {str(e)}")
    
    async def publish_job_deleted(self, job_id: int, job_title: str):
        """Publish event when a job is deleted"""
        try:
            event_data = {
                "job_id": job_id,
                "job_title": job_title,
                "deleted_at": datetime.utcnow().isoformat()
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.JOB_DELETED,
                data=event_data
            )
            
            logger.info(f"Published job deleted event for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish job deleted event: {str(e)}")
    
    # User-related events
    async def publish_user_registered(self, user: User):
        """Publish event when a new user registers"""
        try:
            event_data = {
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "is_admin": user.is_admin,
                "registered_at": user.created_at.isoformat() if user.created_at else None
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.USER_REGISTERED,
                data=event_data
            )
            
            logger.info(f"Published user registered event for user {user.id}: {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to publish user registered event: {str(e)}")
    
    async def publish_user_login(self, user: User, login_metadata: Dict[str, Any]):
        """Publish event when user logs in"""
        try:
            event_data = {
                "user_id": user.id,
                "email": user.email,
                "login_time": datetime.utcnow().isoformat(),
                "metadata": login_metadata
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.USER_LOGIN,
                data=event_data
            )
            
            logger.info(f"Published user login event for user {user.id}")
            
        except Exception as e:
            logger.error(f"Failed to publish user login event: {str(e)}")
    
    async def publish_user_profile_updated(self, user_id: int, updated_fields: List[str], profile_data: Dict[str, Any]):
        """Publish event when user profile is updated"""
        try:
            event_data = {
                "user_id": user_id,
                "updated_fields": updated_fields,
                "profile_data": profile_data,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.USER_PROFILE_UPDATED,
                data=event_data
            )
            
            logger.info(f"Published user profile updated event for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish user profile updated event: {str(e)}")
    
    # ML/AI-related events
    async def publish_job_analysis_request(self, job_ids: List[int], analysis_type: str = "standard"):
        """Request ML analysis for jobs"""
        try:
            event_data = {
                "job_ids": job_ids,
                "analysis_type": analysis_type,
                "requested_at": datetime.utcnow().isoformat(),
                "requester_service": self.service_name
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.JOB_ANALYSIS_REQUESTED,
                data=event_data
            )
            
            logger.info(f"Published job analysis request for {len(job_ids)} jobs")
            
        except Exception as e:
            logger.error(f"Failed to publish job analysis request: {str(e)}")
    
    async def publish_llm_processing_request(
        self, 
        request_type: str, 
        input_data: Dict[str, Any],
        user_id: Optional[int] = None
    ):
        """Request LLM processing"""
        try:
            event_data = {
                "request_type": request_type,
                "input_data": input_data,
                "user_id": user_id,
                "requested_at": datetime.utcnow().isoformat(),
                "requester_service": self.service_name
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.LLM_PROCESSING_REQUESTED,
                data=event_data
            )
            
            logger.info(f"Published LLM processing request: {request_type}")
            
        except Exception as e:
            logger.error(f"Failed to publish LLM processing request: {str(e)}")
    
    # System events
    async def publish_cleanup_request(self, cleanup_type: str = "full", parameters: Dict[str, Any] = None):
        """Request system cleanup"""
        try:
            event_data = {
                "cleanup_type": cleanup_type,
                "parameters": parameters or {},
                "requested_at": datetime.utcnow().isoformat(),
                "requester_service": self.service_name
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.CLEANUP_REQUESTED,
                data=event_data
            )
            
            logger.info(f"Published cleanup request: {cleanup_type}")
            
        except Exception as e:
            logger.error(f"Failed to publish cleanup request: {str(e)}")
    
    async def publish_health_check_failed(self, component: str, error_details: Dict[str, Any]):
        """Publish health check failure event"""
        try:
            event_data = {
                "component": component,
                "error_details": error_details,
                "failed_at": datetime.utcnow().isoformat(),
                "service": self.service_name
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.HEALTH_CHECK_FAILED,
                data=event_data
            )
            
            logger.info(f"Published health check failure for component: {component}")
            
        except Exception as e:
            logger.error(f"Failed to publish health check failure: {str(e)}")
    
    # Notification events
    async def publish_email_request(
        self, 
        recipient: str, 
        subject: str, 
        template: str, 
        data: Dict[str, Any],
        priority: str = "normal"
    ):
        """Request email notification"""
        try:
            event_data = {
                "recipient": recipient,
                "subject": subject,
                "template": template,
                "template_data": data,
                "priority": priority,
                "requested_at": datetime.utcnow().isoformat()
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.EMAIL_REQUEST,
                data=event_data
            )
            
            logger.info(f"Published email request to {recipient}: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to publish email request: {str(e)}")
    
    async def publish_alert(self, alert_type: str, message: str, severity: str = "info", metadata: Dict[str, Any] = None):
        """Publish system alert"""
        try:
            event_data = {
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "metadata": metadata or {},
                "triggered_at": datetime.utcnow().isoformat(),
                "source_service": self.service_name
            }
            
            await self.message_broker.publish_event(
                event_type=EventType.ALERT_TRIGGERED,
                data=event_data
            )
            
            logger.info(f"Published alert: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to publish alert: {str(e)}")


# Global event publisher instance
_event_publisher = None


def get_event_publisher(service_name: str = "core-service") -> EventPublisher:
    """Get global event publisher instance"""
    global _event_publisher
    
    if _event_publisher is None:
        _event_publisher = EventPublisher(service_name)
    
    return _event_publisher


# Convenience functions for common events
async def publish_job_scraped(job: Job, scraping_source: str = "unknown"):
    """Convenience function to publish job scraped event"""
    publisher = get_event_publisher()
    await publisher.publish_job_scraped(job, scraping_source)


async def publish_user_registered(user: User):
    """Convenience function to publish user registered event"""
    publisher = get_event_publisher()
    await publisher.publish_user_registered(user)


async def publish_job_analysis_request(job_ids: List[int], analysis_type: str = "standard"):
    """Convenience function to request job analysis"""
    publisher = get_event_publisher()
    await publisher.publish_job_analysis_request(job_ids, analysis_type)