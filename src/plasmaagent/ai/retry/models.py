from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AttemptStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class RetryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: int = Field(ge=1, le=20, default=3)
    base_delay_seconds: float = Field(ge=0.0, le=60.0, default=1.0)
    max_delay_seconds: float = Field(ge=0.0, le=3600.0, default=60.0)
    backoff_factor: float = Field(ge=1.0, le=10.0, default=2.0)
    jitter: bool = Field(default=True)
    retryable_exceptions: tuple[str, ...] = Field(default_factory=tuple)
    retry_on_exit_codes: tuple[int, ...] = Field(default_factory=tuple)

    @field_validator("max_delay_seconds")
    @classmethod
    def _max_delay_gte_base(cls, v: float, info: Any) -> float:
        base = info.data.get("base_delay_seconds")
        if base is not None and v < base:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        return v


class AttemptResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_number: int = Field(ge=1)
    status: AttemptStatus
    output: str = ""
    error: str = ""
    exit_code: Optional[int] = None
    duration_ms: int = Field(ge=0, default=0)
    delay_before_ms: int = Field(ge=0, default=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exception_type: Optional[str] = None

    def is_success(self) -> bool:
        return self.status == AttemptStatus.SUCCESS

    def is_failure(self) -> bool:
        return self.status == AttemptStatus.FAILED


class RetryResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    config: RetryConfig
    attempts: tuple[AttemptResult, ...] = Field(default_factory=tuple)
    final_status: AttemptStatus
    total_duration_ms: int = Field(ge=0, default=0)
    total_attempts: int = Field(ge=0, default=0)

    @property
    def succeeded(self) -> bool:
        return self.final_status == AttemptStatus.SUCCESS

    @property
    def last_attempt(self) -> Optional[AttemptResult]:
        return self.attempts[-1] if self.attempts else None

    def failure_count(self) -> int:
        return sum(1 for a in self.attempts if a.is_failure())
