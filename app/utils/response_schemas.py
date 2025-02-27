from pydantic import BaseModel
from typing import Optional, Any


class ScrapeResponse(BaseModel):
    message: str
    status: str
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskErrorResponse(BaseModel):
    detail: str
