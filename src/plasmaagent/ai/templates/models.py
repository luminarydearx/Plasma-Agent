from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateSource(str, Enum):
    USER_CREATED = "user_created"
    SYSTEM_DEFAULT = "system_default"
    LEARNED = "learned"
    IMPORTED = "imported"


class TemplateCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern_name: str = Field(min_length=1, max_length=100)
    commands: tuple[str, ...] = Field(min_length=1)
    frequency: int = Field(ge=0, default=0)
    success_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    avg_duration_ms: int = Field(ge=0, default=0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source: TemplateSource = Field(default=TemplateSource.LEARNED)
    sample_task_ids: tuple[str, ...] = Field(default_factory=tuple)
    discovered_at: datetime = Field(default_factory=datetime.now)


class LearnedTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_name: str = Field(min_length=1, max_length=200)
    pattern_regex: str = Field(min_length=1, max_length=1000)
    commands: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    frequency: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    source: TemplateSource = Field(default=TemplateSource.LEARNED)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class LearningReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_tasks_analyzed: int = Field(ge=0)
    successful_tasks: int = Field(ge=0)
    candidates_found: int = Field(ge=0)
    new_templates: int = Field(ge=0)
    updated_templates: int = Field(ge=0)
    candidates: tuple[TemplateCandidate, ...] = Field(default_factory=tuple)
    analysis_duration_ms: int = Field(ge=0, default=0)
    completed_at: datetime = Field(default_factory=datetime.now)


class TemplateVersionCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: UUID
    commands: tuple[str, ...] = Field(min_length=1)
    pattern_name: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    change_description: str | None = Field(default=None, max_length=2000)
    created_by: str | None = Field(default=None, max_length=100)


class TemplateVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    template_id: UUID
    version_number: int = Field(ge=1)
    commands: tuple[str, ...] = Field(min_length=1)
    pattern_name: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    change_description: str | None = None
    created_at: datetime
    created_by: str | None = None


class RollbackReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: UUID
    from_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    new_version_number: int = Field(ge=1)
    rolled_back_at: datetime = Field(default_factory=datetime.now)
    success: bool = True
