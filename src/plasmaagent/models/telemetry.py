from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TelemetryBase(BaseModel):
    event_type: str = Field(..., max_length=100)
    payload: dict[str, Any]


class TelemetryCreate(TelemetryBase):
    pass


class Telemetry(TelemetryBase):
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True
