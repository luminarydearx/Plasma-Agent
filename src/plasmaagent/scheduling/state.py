from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SchedulerStateBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_running: bool = False
    last_check_at: datetime | None = None
    active_task_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SchedulerState(SchedulerStateBase):
    id: UUID
    updated_at: datetime
