from __future__ import annotations

from enum import Enum
from uuid import UUID
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SuggestionType(str, Enum):
    NEXT_ACTION = "next_action"
    SIMILAR_TASK = "similar_task"
    ANOMALY = "anomaly"
    PERFORMANCE = "performance"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID
    suggestion_type: SuggestionType
    priority: Priority
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    related_task_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(str(v)) > 10000:
            raise ValueError("metadata exceeds 10000 characters")
        return v


class SimilarTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: UUID
    task_name: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    common_commands: int = Field(ge=0)
    last_executed: datetime | None = None


class AnomalyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: UUID
    anomaly_type: str = Field(min_length=1, max_length=100)
    severity: Priority
    description: str = Field(min_length=1, max_length=2000)
    baseline_value: float
    observed_value: float
    deviation_factor: float = Field(ge=0.0)
    recommendations: list[str] = Field(default_factory=list)

    @field_validator("recommendations")
    @classmethod
    def validate_recommendations(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("too many recommendations (max 20)")
        for r in v:
            if len(r) > 500:
                raise ValueError("recommendation exceeds 500 characters")
        return v


class PerformanceHint(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: UUID
    hint_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    estimated_savings_ms: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    affected_commands: list[int] = Field(default_factory=list)


class SuggestionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    task_id: UUID | None = None
    include_next_actions: bool = True
    include_similar: bool = True
    include_anomalies: bool = True
    include_performance: bool = True
    max_similar: int = Field(default=5, ge=1, le=50)
    anomaly_threshold: float = Field(default=2.0, ge=1.0, le=10.0)


class SuggestionBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendations: list[Recommendation] = Field(default_factory=list)
    similar_tasks: list[SimilarTask] = Field(default_factory=list)
    anomalies: list[AnomalyReport] = Field(default_factory=list)
    performance_hints: list[PerformanceHint] = Field(default_factory=list)
    total_suggestions: int = Field(ge=0)
    generated_at: datetime
