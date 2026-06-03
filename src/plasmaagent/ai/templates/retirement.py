from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class TemplateRetirementBase(BaseModel):
    template_name: str = Field(max_length=255)
    pattern: Optional[str] = None
    reason: str = Field(max_length=100)
    success_rate: float = Field(ge=0.0, le=1.0)
    total_uses: int = Field(ge=0)
    avg_execution_time_ms: Optional[float] = Field(default=None, ge=0.0)


class TemplateRetirementCreate(TemplateRetirementBase):
    metadata: Optional[Dict[str, Any]] = None


class TemplateRetirement(TemplateRetirementBase):
    id: int
    retired_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RetirementScanRequest(BaseModel):
    success_rate_threshold: float = Field(ge=0.0, le=1.0, default=0.5)
    min_uses_threshold: int = Field(ge=5, default=10)
    max_execution_time_ms: Optional[float] = Field(default=None, ge=0.0)
    scan_period_days: int = Field(ge=1, le=365, default=30)


class RetirementScanReport(BaseModel):
    scanned_at: datetime
    success_rate_threshold: float
    min_uses_threshold: int
    max_execution_time_ms: Optional[float]
    candidates_found: int
    retired_count: int
    skipped_count: int
    retired_templates: List[str]
    skipped_templates: List[Dict[str, str]]
    scan_duration_ms: int
