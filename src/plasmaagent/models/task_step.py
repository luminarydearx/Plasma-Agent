from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskStepBase(BaseModel):
    step_order: int = Field(..., ge=1)
    command: str


class TaskStepCreate(TaskStepBase):
    task_id: UUID


class TaskStep(TaskStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    status: str
    output: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
