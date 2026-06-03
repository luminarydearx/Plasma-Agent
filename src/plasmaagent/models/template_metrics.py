from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateMetricsBase(BaseModel):
    template_name: str = Field(..., max_length=255)
    pattern: str = Field(..., max_length=500)
    usage_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    avg_confidence: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("1.00"))
    total_generation_time_ms: int = Field(default=0, ge=0)
    last_used_at: Optional[datetime] = None


class TemplateMetricsCreate(TemplateMetricsBase):
    pass


class TemplateMetricsUpdate(BaseModel):
    usage_count: Optional[int] = None
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    avg_confidence: Optional[Decimal] = None
    total_generation_time_ms: Optional[int] = None
    last_used_at: Optional[datetime] = None


class TemplateMetrics(TemplateMetricsBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
