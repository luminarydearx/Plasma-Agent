"""Data models for telemetry."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TelemetryBase(BaseModel):
    """Base telemetry model."""

    event_type: str = Field(..., max_length=100, description="Event type")
    payload: dict[str, Any] = Field(..., description="Event payload")


class TelemetryCreate(TelemetryBase):
    """Model for creating a telemetry entry."""

    pass


class Telemetry(TelemetryBase):
    """Complete telemetry model."""

    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True
