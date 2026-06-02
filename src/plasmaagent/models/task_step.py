"""Data models for task steps."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStepBase(BaseModel):
    """Base step model."""

    step_order: int = Field(..., ge=1, description="Execution order")
    command: str = Field(..., description="Shell command to execute")


class TaskStepCreate(TaskStepBase):
    """Model for creating a step."""

    task_id: UUID


class TaskStep(TaskStepBase):
    """Complete step model."""

    id: UUID
    task_id: UUID
    status: str
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True
