"""Data models for execution logs."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionLogBase(BaseModel):
    """Base log model."""

    log_level: str = Field(..., max_length=20, description="Log level")
    message: str = Field(..., description="Log message")


class ExecutionLogCreate(ExecutionLogBase):
    """Model for creating a log entry."""

    task_id: UUID
    step_id: Optional[UUID] = None


class ExecutionLog(ExecutionLogBase):
    """Complete log model."""

    id: UUID
    task_id: UUID
    step_id: Optional[UUID] = None
    timestamp: datetime

    class Config:
        from_attributes = True
