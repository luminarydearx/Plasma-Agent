from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionLogBase(BaseModel):
    log_level: str = Field(..., max_length=20)
    message: str


class ExecutionLogCreate(ExecutionLogBase):
    task_id: UUID
    step_id: Optional[UUID] = None


class ExecutionLog(ExecutionLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    step_id: Optional[UUID] = None
    timestamp: datetime
