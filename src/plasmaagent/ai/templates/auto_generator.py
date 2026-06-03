from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class TemplateCandidateBase(BaseModel):
    pattern: str = Field(max_length=500)
    example_input: str = Field(max_length=2000)
    generated_commands: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    frequency: int = Field(ge=1)


class TemplateCandidateCreate(TemplateCandidateBase):
    source_task_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class TemplateCandidate(TemplateCandidateBase):
    id: int
    status: str = Field(default="pending")
    source_task_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateDetectionRequest(BaseModel):
    min_frequency: int = Field(ge=2, default=3)
    similarity_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    scan_period_days: int = Field(ge=1, le=365, default=7)


class CandidateDetectionReport(BaseModel):
    scanned_at: datetime
    patterns_detected: int
    candidates_generated: int
    duplicate_skipped: int
    scan_duration_ms: int
    new_candidates: List[str]
