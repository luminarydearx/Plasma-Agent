"""Data models for tasks."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    """Base task model."""

    name: str = Field(..., max_length=255, description="Task name")
    description: Optional[str] = Field(None, description="Task description")


class TaskCreate(TaskBase):
    """Model for creating a task."""

    pass


class TaskUpdate(BaseModel):
    """Model for updating a task."""

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None


class Task(TaskBase):
    """Complete task model."""

    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskWithSteps(Task):
    """Task model with associated steps."""

    steps: list = Field(default_factory=list)
