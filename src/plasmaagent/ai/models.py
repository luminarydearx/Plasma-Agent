from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class GeneratedTask(BaseModel):
    name: str = Field(..., description="Task name")
    description: str = Field("", description="Task description")
    commands: list[str] = Field(default_factory=list, description="Commands to execute")
    schedule: Optional[str] = Field(None, description="Cron-like schedule")
    complexity: TaskComplexity = Field(default=TaskComplexity.SIMPLE, description="Task complexity")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Generation confidence score")
    template_used: Optional[str] = Field(None, description="Template name if used")
    parameters: dict = Field(default_factory=dict, description="Extracted parameters")


class TaskGenerationRequest(BaseModel):
    natural_language: str = Field(..., description="Natural language input")
    context: dict = Field(default_factory=dict, description="Additional context")


class TaskGenerationResponse(BaseModel):
    tasks: list[GeneratedTask] = Field(default_factory=list, description="Generated tasks")
    provider_used: str = Field(..., description="Provider that generated the tasks")
    parsing_time_ms: float = Field(..., description="Time taken to parse input")
    generation_time_ms: float = Field(..., description="Time taken to generate tasks")
    total_time_ms: float = Field(..., description="Total processing time")


class TaskAnalysis(BaseModel):
    task_id: str
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0-1)")
    avg_duration_ms: float = Field(..., description="Average execution duration")
    failure_patterns: list[str] = Field(default_factory=list, description="Common failure patterns")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions")


class ProviderInfo(BaseModel):
    name: str
    description: str
    is_active: bool
    supports_generation: bool
    supports_analysis: bool
    supports_suggestions: bool
