from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ReasoningRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    natural_language: str = Field(min_length=1, max_length=10000)
    session_id: str | None = None
    context_variables: dict[str, Any] = Field(default_factory=dict)
    max_parallel: int = Field(default=5, ge=1, le=50)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=300.0, ge=0.1, le=86400.0)
    fail_fast: bool = True


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str = Field(min_length=1, max_length=100)
    natural_language: str = Field(min_length=1, max_length=2000)
    status: StepStatus
    output: str | None = None
    error: str | None = None
    exit_code: int | None = None
    duration_ms: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ReasoningResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=100)
    original_input: str = Field(min_length=1)
    total_steps: int = Field(ge=0)
    completed_steps: int = Field(ge=0)
    failed_steps: int = Field(ge=0)
    skipped_steps: int = Field(ge=0)
    step_results: tuple[StepResult, ...] = Field(default_factory=tuple)
    context_variables: dict[str, Any] = Field(default_factory=dict)
    total_duration_ms: int = Field(ge=0)
    decomposition_time_ms: float = Field(ge=0.0)
    success: bool
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class ReasoningPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=100)
    original_input: str = Field(min_length=1)
    total_steps: int = Field(ge=0)
    execution_mode: str = Field(min_length=1, max_length=50)
    parallel_groups: int = Field(ge=0)
    estimated_duration_ms: int = Field(ge=0)
    steps: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=datetime.now)
