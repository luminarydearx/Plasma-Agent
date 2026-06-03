from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    step_id: str = Field(..., min_length=1, max_length=100)
    status: StepStatus
    output: Optional[str] = Field(default=None, max_length=10000)
    error: Optional[str] = Field(default=None, max_length=5000)
    exit_code: Optional[int] = None
    duration_ms: int = Field(default=0, ge=0, le=86400000)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def is_success(self) -> bool:
        return self.status == StepStatus.COMPLETED and self.exit_code == 0
    
    def is_failure(self) -> bool:
        return self.status in (StepStatus.FAILED, StepStatus.CANCELLED)


class ParallelGroup(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    group_id: str = Field(..., min_length=1, max_length=100)
    step_ids: list[str] = Field(..., min_length=1, max_length=50)
    timeout_seconds: float = Field(default=300.0, gt=0, le=86400)
    max_concurrent: int = Field(default=10, gt=0, le=100)
    fail_fast: bool = Field(default=True)
    
    def __post_init__(self):
        if len(set(self.step_ids)) != len(self.step_ids):
            raise ValueError(f"Duplicate step IDs in group {self.group_id}")


class ParallelResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    group_id: str = Field(..., min_length=1, max_length=100)
    results: list[StepResult] = Field(..., max_length=100)
    total_duration_ms: int = Field(default=0, ge=0, le=86400000)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    cancelled_count: int = Field(default=0, ge=0)
    
    @classmethod
    def from_results(
        cls,
        group_id: str,
        results: list[StepResult],
        total_duration_ms: int
    ) -> "ParallelResult":
        success_count = sum(1 for r in results if r.is_success())
        failure_count = sum(1 for r in results if r.status == StepStatus.FAILED)
        cancelled_count = sum(1 for r in results if r.status == StepStatus.CANCELLED)
        
        return cls(
            group_id=group_id,
            results=results,
            total_duration_ms=total_duration_ms,
            success_count=success_count,
            failure_count=failure_count,
            cancelled_count=cancelled_count,
        )
    
    def all_succeeded(self) -> bool:
        return self.failure_count == 0 and self.cancelled_count == 0
    
    def any_failed(self) -> bool:
        return self.failure_count > 0
    
    def get_failed_steps(self) -> list[StepResult]:
        return [r for r in self.results if r.is_failure()]
