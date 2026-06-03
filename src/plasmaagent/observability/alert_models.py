from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCondition(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    RESOLVED = "resolved"
    DISABLED = "disabled"


class AlertRuleBase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    metric_name: str = Field(..., min_length=1, max_length=100)
    condition: AlertCondition
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    webhook_url: str = Field(..., min_length=1, max_length=2000)
    enabled: bool = True
    cooldown_seconds: int = Field(default=300, ge=0, le=86400)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRule(AlertRuleBase):
    id: UUID
    status: AlertStatus = AlertStatus.ACTIVE
    last_triggered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    rule_name: str
    severity: AlertSeverity
    metric_name: str
    metric_value: float
    threshold: float
    condition: AlertCondition
    message: str = Field(max_length=2000)
    webhook_url: str
    webhook_status: str = "pending"
    webhook_response: str | None = None
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class AlertRuleUpdate(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    threshold: float | None = None
    severity: AlertSeverity | None = None
    webhook_url: str | None = Field(default=None, min_length=1, max_length=2000)
    enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v
