# ML Service RabbitMQ Integration Guide

This document explains how the ML microservice should integrate with the Job Scraper service using RabbitMQ for event-driven communication, replacing the previous direct API calls.

## 🔄 **Migration from API to RabbitMQ**

### **Before (Deprecated API Approach)**
```python
# OLD: Direct HTTP API call
import requests

response = requests.get(
    f"http://job-scraper:8000/api/v1/jobs/match/{job_id}",
    headers={"Authorization": f"Bearer {token}"}
)
job_data = response.json()
```

### **After (New RabbitMQ Approach)**
```python
# NEW: Event-driven RabbitMQ communication
import pika
import json
import uuid
from datetime import datetime

# Send job data request event
def request_job_data(job_id: int, ml_service_id: str = "ml-service"):
    connection = pika.BlockingConnection(
        pika.URLParameters("amqp://guest:guest@rabbitmq:5672/")
    )
    channel = connection.channel()
    
    # Create request message
    request_message = {
        "event_id": str(uuid.uuid4()),
        "event_type": "ml.job_data_requested",
        "source_service": ml_service_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "job_id": job_id,
            "ml_service_id": ml_service_id,
            "request_id": str(uuid.uuid4()),
            "additional_fields": ["category", "skills", "requirements"]  # Optional
        }
    }
    
    # Publish request
    channel.basic_publish(
        exchange="job_scraper_events",
        routing_key="ml.job_data_requested",
        body=json.dumps(request_message)
    )
    
    connection.close()
```

## 📡 **Event Types**

### **1. Single Job Data Request**
- **Event Type**: `ml.job_data_requested`
- **Routing Key**: `ml.job_data_requested`
- **Response Event**: `ml.job_data_response`
- **Response Routing Key**: `ml.{ml_service_id}.job_data_response`

### **2. Bulk Job Data Request**
- **Event Type**: `ml.bulk_job_data_requested`
- **Routing Key**: `ml.bulk_job_data_requested`
- **Response Event**: `ml.bulk_job_data_response`
- **Response Routing Key**: `ml.{ml_service_id}.bulk_job_data_response`

## 📋 **Message Formats**

### **Single Job Data Request**
```json
{
    "event_id": "uuid-string",
    "event_type": "ml.job_data_requested",
    "source_service": "ml-service",
    "timestamp": "2024-01-15T10:30:00Z",
    "correlation_id": "optional-correlation-id",
    "data": {
        "job_id": 123,
        "ml_service_id": "ml-service",
        "request_id": "unique-request-id",
        "additional_fields": ["category", "skills", "requirements"]
    }
}
```

### **Single Job Data Response**
```json
{
    "event_id": "uuid-string",
    "event_type": "ml.job_data_response",
    "source_service": "core-service",
    "timestamp": "2024-01-15T10:30:01Z",
    "correlation_id": "matching-correlation-id",
    "data": {
        "request_id": "matching-request-id",
        "ml_service_id": "ml-service",
        "status": "success",
        "job_data": {
            "id": 123,
            "title": "Senior Python Developer",
            "company": "Tech Corp",
            "location": "Remote",
            "job_type": "Full-time",
            "experience": "3-5 years",
            "description": "Job description text...",
            "salary": "80000-120000",
            "currency": "USD",
            "posted_date": "2024-01-10T00:00:00Z",
            "scraped_at": "2024-01-10T12:00:00Z",
            "source": "indeed",
            "url": "https://example.com/job/123",
            
            // ML-optimized fields
            "text_length": 1250,
            "title_words": 3,
            "has_salary": true,
            "is_remote": true,
            "company_size_category": "medium",
            "experience_level_numeric": 4.0
        }
    }
}
```

### **Bulk Job Data Request**
```json
{
    "event_id": "uuid-string",
    "event_type": "ml.bulk_job_data_requested",
    "source_service": "ml-service",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "ml_service_id": "ml-service",
        "request_id": "bulk-request-id",
        "filters": {
            "job_ids": [123, 456, 789],  // Optional: specific IDs
            "limit": 100,               // Max 1000
            "offset": 0,
            "location": ["Remote", "New York"],
            "job_type": ["Full-time", "Contract"],
            "experience": ["3-5 years", "5+ years"],
            "date_from": "2024-01-01",
            "date_to": "2024-01-15"
        },
        "additional_fields": ["category", "skills"]
    }
}
```

### **Bulk Job Data Response**
```json
{
    "event_id": "uuid-string",
    "event_type": "ml.bulk_job_data_response",
    "source_service": "core-service",
    "timestamp": "2024-01-15T10:30:02Z",
    "data": {
        "request_id": "bulk-request-id",
        "ml_service_id": "ml-service",
        "status": "success",
        "bulk_data": {
            "jobs": [
                // Array of job objects (same format as single job data)
            ],
            "total": 1500,
            "limit": 100,
            "offset": 0,
            "request_id": "bulk-request-id"
        }
    }
}
```

### **Error Response**
```json
{
    "event_id": "uuid-string",
    "event_type": "ml.job_data_response",
    "source_service": "core-service",
    "timestamp": "2024-01-15T10:30:01Z",
    "data": {
        "request_id": "matching-request-id",
        "ml_service_id": "ml-service",
        "status": "error",
        "error": "Job with id 999 not found"
    }
}
```

## 🐍 **Python ML Service Implementation**

### **1. Install Dependencies**
```bash
pip install pika asyncio aio-pika
```

### **2. ML Service RabbitMQ Client**
```python
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable
import aio_pika
from aio_pika import connect, Message, DeliveryMode

class MLJobDataClient:
    def __init__(self, rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.ml_service_id = "ml-service"
        self.response_handlers = {}
    
    async def connect(self):
        """Initialize RabbitMQ connection"""
        self.connection = await connect(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        
        # Declare exchange
        self.exchange = await self.channel.declare_exchange(
            "job_scraper_events", 
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Setup response queue
        self.response_queue = await self.channel.declare_queue(
            f"ml.{self.ml_service_id}.responses",
            durable=True
        )
        
        # Bind response queue to receive responses
        await self.response_queue.bind(
            self.exchange, 
            f"ml.{self.ml_service_id}.job_data_response"
        )
        await self.response_queue.bind(
            self.exchange, 
            f"ml.{self.ml_service_id}.bulk_job_data_response"
        )
        
        # Start consuming responses
        await self.response_queue.consume(self._handle_response)
    
    async def request_job_data(
        self, 
        job_id: int, 
        additional_fields: Optional[List[str]] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """Request single job data"""
        request_id = str(uuid.uuid4())
        
        if callback:
            self.response_handlers[request_id] = callback
        
        message_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ml.job_data_requested",
            "source_service": self.ml_service_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "job_id": job_id,
                "ml_service_id": self.ml_service_id,
                "request_id": request_id,
                "additional_fields": additional_fields or []
            }
        }
        
        message = Message(
            json.dumps(message_data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        
        await self.exchange.publish(
            message, 
            routing_key="ml.job_data_requested"
        )
        
        return request_id
    
    async def request_bulk_job_data(
        self,
        filters: Optional[Dict] = None,
        additional_fields: Optional[List[str]] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """Request bulk job data"""
        request_id = str(uuid.uuid4())
        
        if callback:
            self.response_handlers[request_id] = callback
        
        message_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ml.bulk_job_data_requested",
            "source_service": self.ml_service_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "ml_service_id": self.ml_service_id,
                "request_id": request_id,
                "filters": filters or {},
                "additional_fields": additional_fields or []
            }
        }
        
        message = Message(
            json.dumps(message_data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        
        await self.exchange.publish(
            message, 
            routing_key="ml.bulk_job_data_requested"
        )
        
        return request_id
    
    async def _handle_response(self, message: aio_pika.Message):
        """Handle incoming response messages"""
        try:
            data = json.loads(message.body.decode())
            request_id = data.get("data", {}).get("request_id")
            
            if request_id in self.response_handlers:
                callback = self.response_handlers.pop(request_id)
                await callback(data)
            
            await message.ack()
        except Exception as e:
            print(f"Error handling response: {e}")
            await message.nack()
    
    async def close(self):
        """Close connection"""
        if self.connection:
            await self.connection.close()
```

### **3. Example Usage in ML Service**
```python
async def main():
    # Initialize client
    client = MLJobDataClient("amqp://guest:guest@rabbitmq:5672/")
    await client.connect()
    
    # Define response handler
    async def handle_job_data_response(response_data):
        if response_data["data"]["status"] == "success":
            job_data = response_data["data"]["job_data"]
            print(f"Received job data: {job_data['title']}")
            
            # Process job data for ML
            await process_job_for_ml(job_data)
        else:
            print(f"Error: {response_data['data']['error']}")
    
    # Request single job data
    request_id = await client.request_job_data(
        job_id=123,
        additional_fields=["category", "skills"],
        callback=handle_job_data_response
    )
    
    # Request bulk job data
    bulk_request_id = await client.request_bulk_job_data(
        filters={
            "limit": 50,
            "location": ["Remote"],
            "job_type": ["Full-time"]
        },
        callback=handle_bulk_job_data_response
    )
    
    # Keep service running
    await asyncio.sleep(60)
    await client.close()

async def process_job_for_ml(job_data):
    """Process job data for ML model"""
    # Extract features
    features = {
        "title_length": len(job_data["title"]),
        "description_length": job_data["text_length"],
        "is_remote": job_data["is_remote"],
        "experience_numeric": job_data["experience_level_numeric"],
        "company_size": job_data["company_size_category"]
    }
    
    # Run ML processing
    prediction = await your_ml_model.predict(features)
    
    print(f"ML prediction for job {job_data['id']}: {prediction}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🔧 **Configuration**

### **Environment Variables for ML Service**
```env
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ML_SERVICE_ID=ml-service
JOB_SCRAPER_EXCHANGE=job_scraper_events
```

### **Docker Compose Integration**
```yaml
version: '3.8'
services:
  ml-service:
    build: .
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
    depends_on:
      - rabbitmq
    networks:
      - microservices

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
    networks:
      - microservices

networks:
  microservices:
    driver: bridge
```

## 🚀 **Benefits of RabbitMQ Integration**

1. **Decoupling**: ML service doesn't need to know job scraper's HTTP endpoints
2. **Reliability**: Messages are persisted and guaranteed delivery
3. **Scalability**: Multiple ML service instances can consume from the same queue
4. **Performance**: Asynchronous processing without blocking HTTP requests
5. **Fault Tolerance**: Automatic retry and dead letter queue handling
6. **Event-Driven**: Real-time data streaming instead of polling

## 🔍 **Monitoring & Debugging**

### **RabbitMQ Management UI**
- Access: `http://localhost:15672`
- Default credentials: `guest/guest`
- Monitor queues, exchanges, and message flow

### **Queue Names**
- Request Queue: `core.ml_job_data_requested`
- Bulk Request Queue: `core.ml_bulk_job_data_requested`
- Response Queue: `ml.{service_id}.responses`

### **Logging**
Both services log all message publishing and consumption for debugging.

## 📋 **Migration Checklist**

- [ ] Update ML service to use RabbitMQ client
- [ ] Test single job data requests
- [ ] Test bulk job data requests
- [ ] Implement error handling
- [ ] Set up monitoring
- [ ] Remove old HTTP API calls
- [ ] Update deployment configurations
- [ ] Test end-to-end flow

This event-driven architecture provides a robust, scalable foundation for ML service integration with the job scraper microservice.