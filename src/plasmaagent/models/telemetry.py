from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TelemetryBase(BaseModel):
    event_type: str = Field(..., max_length=100)
    payload: dict[str, Any]


class TelemetryCreate(TelemetryBase):
    pass


class Telemetry(TelemetryBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
