"""
ML Job Service - Handles job data serving to ML microservice via RabbitMQ
Replaces direct API calls with event-driven architecture
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from uuid import uuid4

from ..core.logger import logger
from ..core.message_broker import EventType, EventMessage, get_message_broker
from ..db.repositories.job_repository import JobRepository
from ..schemas.job import JobResponse
from ..core.cache import InternalCache
from ..models.job import Job


class MLJobService:
    """Service for handling ML microservice job data requests via RabbitMQ"""

    def __init__(self):
        self.message_broker = get_message_broker("core-service")

    async def handle_job_data_request(
        self, event_message: EventMessage, db: Session
    ) -> None:
        """
        Handle job data request from ML service via RabbitMQ

        Expected event_message.data format:
        {
            "job_id": int,
            "request_id": str,  # For tracking the request
            "ml_service_id": str,  # Identifier for the requesting ML service
            "additional_fields": List[str]  # Optional: specific fields needed
        }
        """
        try:
            logger.info(
                f"ML Job Service: Received job data request - Event ID: {event_message.event_id}"
            )
            logger.info(f"ML Job Service: Event data: {event_message.data}")

            job_id = event_message.data.get("job_id")
            request_id = event_message.data.get("request_id", str(uuid4()))
            ml_service_id = event_message.data.get("ml_service_id", "unknown")
            additional_fields = event_message.data.get("additional_fields", [])

            logger.info(
                f"ML Job Service: Parsed - job_id: {job_id}, request_id: {request_id}, ml_service_id: {ml_service_id}"
            )

            if not job_id:
                logger.error("ML Job Service: job_id is missing from request")
                await self._send_error_response(
                    request_id,
                    ml_service_id,
                    "job_id is required",
                    event_message.correlation_id,
                )
                return

            logger.info(
                f"Processing job data request for job_id: {job_id} from ML service: {ml_service_id}"
            )

            # Try to get from cache first
            logger.info(f"ML Job Service: Checking cache for job_id: {job_id}")
            cached_job = InternalCache.get_job_data(job_id)
            if cached_job:
                logger.info(
                    f"ML Job Service: Found cached job data for job_id: {job_id}"
                )
                await self._send_job_data_response(
                    cached_job, request_id, ml_service_id, event_message.correlation_id
                )
                return

            # Get job from database
            logger.info(
                f"ML Job Service: Fetching job from database for job_id: {job_id}"
            )
            repo = JobRepository(db)
            job = repo.get_by_id(job_id)

            if not job:
                logger.warning(
                    f"ML Job Service: Job with id {job_id} not found in database"
                )
                await self._send_error_response(
                    request_id,
                    ml_service_id,
                    f"Job with id {job_id} not found",
                    event_message.correlation_id,
                )
                return

            logger.info(
                f"ML Job Service: Found job in database: {job.job_title} - {job.company_name}"
            )

            # Convert to response format
            job_data = self._prepare_job_data_for_ml(job, additional_fields)
            logger.info(
                f"ML Job Service: Prepared job data with {len(job_data)} fields"
            )

            # Cache the result for future requests
            InternalCache.set_job_data(job_id, job_data)

            # Send response back to ML service
            logger.info(f"ML Job Service: Sending response for job_id: {job_id}")
            await self._send_job_data_response(
                job_data, request_id, ml_service_id, event_message.correlation_id
            )

            logger.info(
                f"Successfully sent job data for job_id: {job_id} to ML service: {ml_service_id}"
            )

        except Exception as e:
            logger.error(f"Error handling job data request: {str(e)}")
            request_id = event_message.data.get("request_id", "unknown")
            ml_service_id = event_message.data.get("ml_service_id", "unknown")
            await self._send_error_response(
                request_id,
                ml_service_id,
                f"Internal server error: {str(e)}",
                event_message.correlation_id,
            )

    async def handle_bulk_job_data_request(
        self, event_message: EventMessage, db: Session
    ) -> None:
        """
        Handle bulk job data request from ML service

        Expected event_message.data format:
        {
            "request_id": str,
            "ml_service_id": str,
            "filters": {
                "job_ids": List[int],  # Specific job IDs (optional)
                "limit": int,  # Max number of jobs (default 100)
                "offset": int,  # Pagination offset (default 0)
                "location": List[str],  # Filter by locations (optional)
                "job_type": List[str],  # Filter by job types (optional)
                "experience": List[str],  # Filter by experience levels (optional)
                "date_from": str,  # ISO date string (optional)
                "date_to": str,  # ISO date string (optional)
            },
            "additional_fields": List[str]  # Optional specific fields
        }
        """
        try:
            request_id = event_message.data.get("request_id", str(uuid4()))
            ml_service_id = event_message.data.get("ml_service_id", "unknown")
            filters = event_message.data.get("filters", {})
            additional_fields = event_message.data.get("additional_fields", [])

            logger.info(
                f"Processing bulk job data request from ML service: {ml_service_id}"
            )

            # Extract filters
            job_ids = filters.get("job_ids")
            limit = min(filters.get("limit", 100), 1000)  # Cap at 1000 for performance
            offset = filters.get("offset", 0)
            location = filters.get("location")
            job_type = filters.get("job_type")
            experience = filters.get("experience")
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")

            # Try cache for bulk requests
            cache_key = f"bulk_{hash(str(filters))}"
            cached_result = InternalCache.get_bulk_jobs({"cache_key": cache_key})
            if cached_result:
                logger.debug("Serving cached bulk job data")
                await self._send_bulk_job_data_response(
                    cached_result,
                    request_id,
                    ml_service_id,
                    event_message.correlation_id,
                )
                return

            repo = JobRepository(db)

            if job_ids:
                # Get specific jobs by IDs
                jobs = repo.get_jobs_by_ids(job_ids)
                total = len(jobs)
            else:
                # Get filtered jobs
                jobs, total = repo.get_filtered_jobs(
                    skip=offset,
                    limit=limit,
                    location=location,
                    job_type=job_type,
                    experience=experience,
                    date_from=date_from,
                    date_to=date_to,
                )

            # Prepare job data for ML service
            jobs_data = [
                self._prepare_job_data_for_ml(job, additional_fields) for job in jobs
            ]

            result = {
                "jobs": jobs_data,
                "total": total,
                "limit": limit,
                "offset": offset,
                "request_id": request_id,
            }

            # Cache the result
            InternalCache.set_bulk_jobs(
                {"cache_key": cache_key}, result, ttl=300
            )  # 5 minutes

            await self._send_bulk_job_data_response(
                result, request_id, ml_service_id, event_message.correlation_id
            )

            logger.info(
                f"Successfully sent {len(jobs_data)} jobs to ML service: {ml_service_id}"
            )

        except Exception as e:
            logger.error(f"Error handling bulk job data request: {str(e)}")
            request_id = event_message.data.get("request_id", "unknown")
            ml_service_id = event_message.data.get("ml_service_id", "unknown")
            await self._send_error_response(
                request_id,
                ml_service_id,
                f"Internal server error: {str(e)}",
                event_message.correlation_id,
            )

    def _prepare_job_data_for_ml(
        self, job: Job, additional_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare job data in format optimized for ML service consumption
        """
        # Base job data
        job_data = {
            "id": job.id,
            "title": job.job_title,  # Correct field name
            "company": job.company_name,  # Correct field name
            "location": job.location,
            "job_type": job.job_type,
            "experience": job.experience,
            "description": job.description,
            "salary": job.salary,
            "category": job.category,
            "posting_date": job.posting_date.isoformat() if job.posting_date else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "detail_url": job.detail_url,
            "apply_link": job.apply_link,
        }

        # Add additional fields if requested
        if additional_fields:
            for field in additional_fields:
                if hasattr(job, field):
                    value = getattr(job, field)
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    job_data[field] = value

        # Add ML-specific computed fields
        job_data.update(
            {
                "text_length": len(job.description) if job.description else 0,
                "title_words": len(job.job_title.split()) if job.job_title else 0,
                "has_salary": bool(job.salary),
                "is_remote": (
                    "remote" in job.location.lower() if job.location else False
                ),
                "company_size_category": self._categorize_company_size(
                    job.company_name
                ),
                "experience_level_numeric": self._convert_experience_to_numeric(
                    job.experience
                ),
            }
        )

        return job_data

    def _categorize_company_size(self, company: str) -> str:
        """Categorize company size based on known patterns"""
        if not company:
            return "unknown"

        company_lower = company.lower()
        # Add your company size categorization logic here
        # This is a simple example
        if any(word in company_lower for word in ["startup", "ltd", "llc"]):
            return "small"
        elif any(word in company_lower for word in ["inc", "corp", "pvt"]):
            return "medium"
        elif any(
            word in company_lower
            for word in ["google", "microsoft", "amazon", "apple", "meta"]
        ):
            return "large"
        else:
            return "medium"

    def _convert_experience_to_numeric(self, experience: str) -> Optional[float]:
        """Convert experience string to numeric value for ML processing"""
        if not experience:
            return None

        experience_lower = experience.lower()

        # Extract numeric values from experience strings
        import re

        numbers = re.findall(r"\d+", experience_lower)

        if "entry" in experience_lower or "fresher" in experience_lower:
            return 0.0
        elif "junior" in experience_lower:
            return 1.0
        elif "senior" in experience_lower:
            return 5.0
        elif numbers:
            try:
                return float(numbers[0])
            except ValueError:
                return None
        else:
            return None

    async def _send_job_data_response(
        self,
        job_data: Dict[str, Any],
        request_id: str,
        ml_service_id: str,
        correlation_id: Optional[str],
    ) -> None:
        """Send job data response back to ML service"""
        routing_key = f"ml.{ml_service_id}.job_data_response"
        logger.info(
            f"ML Job Service: Creating response message with routing key: {routing_key}"
        )

        response_message = EventMessage(
            event_id=str(uuid4()),
            event_type=EventType.JOB_DATA_RESPONSE,
            source_service="core-service",
            timestamp=datetime.now().isoformat(),
            data={
                "request_id": request_id,
                "ml_service_id": ml_service_id,
                "job_data": job_data,
                "status": "success",
            },
            correlation_id=correlation_id,
        )

        logger.info(
            f"ML Job Service: Publishing response message for request_id: {request_id}"
        )
        await self.message_broker.publish_message(
            response_message, routing_key=routing_key
        )
        logger.info(f"ML Job Service: Response message published successfully")

    async def _send_bulk_job_data_response(
        self,
        bulk_data: Dict[str, Any],
        request_id: str,
        ml_service_id: str,
        correlation_id: Optional[str],
    ) -> None:
        """Send bulk job data response back to ML service"""
        response_message = EventMessage(
            event_id=str(uuid4()),
            event_type=EventType.BULK_JOB_DATA_RESPONSE,
            source_service="core-service",
            timestamp=datetime.now().isoformat(),
            data={
                "request_id": request_id,
                "ml_service_id": ml_service_id,
                "bulk_data": bulk_data,
                "status": "success",
            },
            correlation_id=correlation_id,
        )

        await self.message_broker.publish_message(
            response_message, routing_key=f"ml.{ml_service_id}.bulk_job_data_response"
        )

    async def _send_error_response(
        self,
        request_id: str,
        ml_service_id: str,
        error_message: str,
        correlation_id: Optional[str],
    ) -> None:
        """Send error response back to ML service"""
        response_message = EventMessage(
            event_id=str(uuid4()),
            event_type=EventType.JOB_DATA_RESPONSE,
            source_service="core-service",
            timestamp=datetime.now().isoformat(),
            data={
                "request_id": request_id,
                "ml_service_id": ml_service_id,
                "status": "error",
                "error": error_message,
            },
            correlation_id=correlation_id,
        )

        await self.message_broker.publish_message(
            response_message, routing_key=f"ml.{ml_service_id}.job_data_response"
        )


# Global service instance
ml_job_service = MLJobService()
