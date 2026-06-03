from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeRange(str, Enum):
    LAST_HOUR = "last_hour"
    LAST_DAY = "last_day"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    ALL_TIME = "all_time"
    CUSTOM = "custom"

    def to_timedelta(self) -> Optional[timedelta]:
        mapping = {
            TimeRange.LAST_HOUR: timedelta(hours=1),
            TimeRange.LAST_DAY: timedelta(days=1),
            TimeRange.LAST_WEEK: timedelta(weeks=1),
            TimeRange.LAST_MONTH: timedelta(days=30),
            TimeRange.ALL_TIME: None,
            TimeRange.CUSTOM: None,
        }
        return mapping[self]


class MetricsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_range: TimeRange = Field(default=TimeRange.LAST_DAY)
    task_id: Optional[UUID] = Field(default=None)
    template_name: Optional[str] = Field(default=None, max_length=200)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    limit: int = Field(default=100, ge=1, le=10000)

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is None:
            return v
        start_time = info.data.get("start_time")
        if start_time is not None and v <= start_time:
            raise ValueError("end_time must be after start_time")
        return v

    def get_time_bounds(self) -> tuple[Optional[datetime], datetime]:
        now = datetime.utcnow()
        if self.time_range == TimeRange.CUSTOM:
            return self.start_time, self.end_time or now
        delta = self.time_range.to_timedelta()
        if delta is None:
            return None, now
        return now - delta, now


class ExecutionMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_executions: int = Field(default=0, ge=0)
    successful_executions: int = Field(default=0, ge=0)
    failed_executions: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_duration_ms: float = Field(default=0.0, ge=0.0)
    min_duration_ms: float = Field(default=0.0, ge=0.0)
    max_duration_ms: float = Field(default=0.0, ge=0.0)
    p50_duration_ms: float = Field(default=0.0, ge=0.0)
    p95_duration_ms: float = Field(default=0.0, ge=0.0)
    p99_duration_ms: float = Field(default=0.0, ge=0.0)
    throughput_per_minute: float = Field(default=0.0, ge=0.0)

    @field_validator("failed_executions")
    @classmethod
    def validate_failed_not_exceed_total(cls, v: int, info) -> int:
        total = info.data.get("total_executions", 0)
        if v > total:
            raise ValueError("failed_executions cannot exceed total_executions")
        return v

    @field_validator("successful_executions")
    @classmethod
    def validate_successful_not_exceed_total(cls, v: int, info) -> int:
        total = info.data.get("total_executions", 0)
        if v > total:
            raise ValueError("successful_executions cannot exceed total_executions")
        return v


class TaskMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: UUID
    task_name: str = Field(max_length=500)
    template_name: Optional[str] = Field(default=None, max_length=200)
    execution: ExecutionMetrics
    last_executed_at: Optional[datetime] = Field(default=None)
    first_executed_at: Optional[datetime] = Field(default=None)


class SystemMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_tasks: int = Field(default=0, ge=0)
    active_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    pending_tasks: int = Field(default=0, ge=0)
    running_tasks: int = Field(default=0, ge=0)
    cancelled_tasks: int = Field(default=0, ge=0)
    overall_execution: ExecutionMetrics
    unique_templates_used: int = Field(default=0, ge=0)
    top_templates: list[dict] = Field(default_factory=list)
    failure_patterns: list[dict] = Field(default_factory=list)
    query_time_ms: float = Field(default=0.0, ge=0.0)

    @field_validator("active_tasks")
    @classmethod
    def validate_active_tasks(cls, v: int, info) -> int:
        total = info.data.get("total_tasks", 0)
        if v > total:
            raise ValueError("active_tasks cannot exceed total_tasks")
        return v
