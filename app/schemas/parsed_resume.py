from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class ParsedResumeCreate(BaseModel):
    raw_text: str
    parsed_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedResumeResponse(BaseModel):
    id: int
    resume_file_path: str | None
    raw_text: str
    parsed_data: dict
    metadata: dict
    uploaded_at: datetime

    class Config:
        orm_mode = True
