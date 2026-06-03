from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MissedRunPolicy = Literal["skip", "run_once", "run_all"]


class TaskPayload(BaseModel):
    commands: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    timeout: int = Field(default=300, ge=1, le=86400)


class TaskBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class TaskCreate(TaskBase):
    payload: Optional[TaskPayload] = None
    cron_expression: Optional[str] = Field(default=None, max_length=100)
    schedule_timezone: Optional[str] = Field(default=None, max_length=50)
    missed_run_policy: MissedRunPolicy = "skip"


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    schedule_timezone: Optional[str] = Field(None, max_length=50)
    missed_run_policy: Optional[MissedRunPolicy] = None
    is_scheduled: Optional[bool] = None


class Task(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    payload: Optional[dict[str, Any]] = None
    cron_expression: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    is_scheduled: bool = False
    schedule_timezone: Optional[str] = None
    missed_run_policy: MissedRunPolicy = "skip"
    created_at: datetime
    updated_at: datetime


class TaskWithSteps(Task):
    steps: list = Field(default_factory=list)


class ScheduledTaskInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    cron_expression: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    status: str
    missed_run_policy: MissedRunPolicy = "skip"
