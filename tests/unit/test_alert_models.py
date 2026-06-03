import pytest
from uuid import uuid4

from plasmaagent.observability.alert_models import (
    AlertCondition,
    AlertEvent,
    AlertRule,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSeverity,
    AlertStatus,
)


class TestAlertRuleCreate:
    def test_valid_creation(self):
        rule = AlertRuleCreate(
            name="High Failure Rate",
            description="Alert when failure rate exceeds 50%",
            metric_name="failure_rate",
            condition=AlertCondition.GREATER_THAN,
            threshold=50.0,
            severity=AlertSeverity.CRITICAL,
            webhook_url="https://hooks.slack.com/test",
            enabled=True,
            cooldown_seconds=300,
        )
        assert rule.name == "High Failure Rate"
        assert rule.threshold == 50.0
        assert rule.severity == AlertSeverity.CRITICAL

    def test_minimal_creation(self):
        rule = AlertRuleCreate(
            name="Test Alert",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com/webhook",
        )
        assert rule.enabled is True
        assert rule.cooldown_seconds == 300
        assert rule.severity == AlertSeverity.WARNING

    def test_invalid_webhook_url(self):
        with pytest.raises(ValueError, match="must start with http"):
            AlertRuleCreate(
                name="Test",
                metric_name="test",
                condition=AlertCondition.EQUALS,
                threshold=1.0,
                webhook_url="ftp://invalid.com",
            )

    def test_name_too_long(self):
        with pytest.raises(ValueError):
            AlertRuleCreate(
                name="x" * 201,
                metric_name="test",
                condition=AlertCondition.EQUALS,
                threshold=1.0,
                webhook_url="https://example.com",
            )

    def test_cooldown_bounds(self):
        with pytest.raises(ValueError):
            AlertRuleCreate(
                name="Test",
                metric_name="test",
                condition=AlertCondition.EQUALS,
                threshold=1.0,
                webhook_url="https://example.com",
                cooldown_seconds=-1,
            )

        with pytest.raises(ValueError):
            AlertRuleCreate(
                name="Test",
                metric_name="test",
                condition=AlertCondition.EQUALS,
                threshold=1.0,
                webhook_url="https://example.com",
                cooldown_seconds=86401,
            )


class TestAlertRule:
    def test_creation_with_id(self):
        rule_id = uuid4()
        rule = AlertRule(
            id=rule_id,
            name="Test Rule",
            metric_name="test_metric",
            condition=AlertCondition.LESS_THAN,
            threshold=10.0,
            webhook_url="https://example.com",
        )
        assert rule.id == rule_id
        assert rule.status == AlertStatus.ACTIVE
        assert rule.last_triggered_at is None


class TestAlertEvent:
    def test_creation(self):
        event = AlertEvent(
            rule_id=uuid4(),
            rule_name="Test Rule",
            severity=AlertSeverity.WARNING,
            metric_name="cpu_usage",
            metric_value=95.0,
            threshold=80.0,
            condition=AlertCondition.GREATER_THAN,
            message="CPU usage exceeded 80%",
            webhook_url="https://example.com",
        )
        assert event.webhook_status == "pending"
        assert event.resolved_at is None

    def test_with_response(self):
        event = AlertEvent(
            rule_id=uuid4(),
            rule_name="Test",
            severity=AlertSeverity.CRITICAL,
            metric_name="test",
            metric_value=100.0,
            threshold=50.0,
            condition=AlertCondition.GREATER_THAN,
            message="Alert triggered",
            webhook_url="https://example.com",
            webhook_status="success",
            webhook_response="Status: 200",
        )
        assert event.webhook_status == "success"


class TestAlertRuleUpdate:
    def test_partial_update(self):
        update = AlertRuleUpdate(
            name="Updated Name",
            threshold=75.0,
        )
        assert update.name == "Updated Name"
        assert update.threshold == 75.0
        assert update.description is None

    def test_invalid_webhook_in_update(self):
        with pytest.raises(ValueError, match="must start with http"):
            AlertRuleUpdate(webhook_url="invalid-url")


class TestAlertEnums:
    def test_severity_values(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_condition_values(self):
        assert AlertCondition.EQUALS.value == "equals"
        assert AlertCondition.GREATER_THAN.value == "greater_than"
        assert AlertCondition.LESS_THAN.value == "less_than"

    def test_status_values(self):
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.TRIGGERED.value == "triggered"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.DISABLED.value == "disabled"
