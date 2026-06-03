from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextVariableType(str, Enum):
    OUTPUT = "output"
    EXIT_CODE = "exit_code"
    ERROR = "error"
    DURATION_MS = "duration_ms"
    STDOUT = "stdout"
    STDERR = "stderr"
    CUSTOM = "custom"


class ContextEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1, max_length=100)
    variable_name: str = Field(min_length=1, max_length=100)
    variable_type: ContextVariableType
    value: Any
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task_id cannot be empty")
        return v.strip()

    @field_validator("variable_name")
    @classmethod
    def validate_variable_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("variable_name cannot be empty")
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError("variable_name must be alphanumeric (underscores and dots allowed)")
        return v.strip()


class TaskExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    output: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = Field(ge=0, default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str = Field(min_length=1, max_length=100)
    entries: tuple[ContextEntry, ...] = Field(default_factory=tuple)
    task_results: tuple[TaskExecutionResult, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=datetime.now)
