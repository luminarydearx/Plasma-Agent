from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskPayload(BaseModel):
    commands: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    timeout: int = 300


class TaskBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class TaskCreate(TaskBase):
    payload: Optional[TaskPayload] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class Task(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class TaskWithSteps(Task):
    steps: list = Field(default_factory=list)
