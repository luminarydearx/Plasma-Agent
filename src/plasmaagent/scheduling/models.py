from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MissedRunPolicy(str, Enum):
    SKIP = "skip"
    CATCH_UP = "catch_up"
    RUN_ONCE = "run_once"


class TaskScheduleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cron_expression: str = Field(..., min_length=1, max_length=100)
    is_scheduled: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    schedule_timezone: str | None = Field(default=None, max_length=50)
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP


class TaskScheduleUpdate(BaseModel):
    cron_expression: str | None = None
    is_scheduled: bool | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    schedule_timezone: str | None = None
    missed_run_policy: MissedRunPolicy | None = None
