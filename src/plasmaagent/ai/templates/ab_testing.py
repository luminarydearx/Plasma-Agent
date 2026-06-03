from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ABTestBase(BaseModel):
    template_name: str = Field(max_length=255)
    version_a_id: UUID
    version_b_id: UUID
    confidence_threshold: float = Field(ge=0.5, le=0.99, default=0.95)
    min_samples: int = Field(ge=10, le=10000, default=100)

class ABTestCreate(ABTestBase):
    pass

class ABTestResult(BaseModel):
    id: int
    ab_test_id: int
    version_id: UUID
    success: bool
    execution_time_ms: int = Field(ge=0)
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ABTest(ABTestBase):
    id: int
    status: str = Field(default='active')
    started_at: datetime
    ended_at: Optional[datetime] = None
    winner_version_id: Optional[UUID] = None
    
    model_config = ConfigDict(from_attributes=True)

class ABTestStats(BaseModel):
    version_id: UUID
    total_samples: int
    successes: int
    failures: int
    success_rate: float
    avg_execution_time_ms: float
    confidence_interval: float

class ABTestAnalysis(BaseModel):
    ab_test_id: int
    template_name: str
    version_a_stats: ABTestStats
    version_b_stats: ABTestStats
    winner_version_id: Optional[UUID]
    confidence: float
    is_significant: bool
    recommendation: str
