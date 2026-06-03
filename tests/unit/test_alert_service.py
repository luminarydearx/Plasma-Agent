import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from plasmaagent.observability.alert_models import (
    AlertCondition,
    AlertRule,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSeverity,
    AlertStatus,
)
from plasmaagent.observability.alert_service import AlertService


class TestAlertServiceCondition:
    @pytest.mark.asyncio
    async def test_evaluate_equals(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.EQUALS, 10.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.EQUALS, 10.0001, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.EQUALS, 10.1, 10.0) is False

    @pytest.mark.asyncio
    async def test_evaluate_not_equals(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.NOT_EQUALS, 10.0, 10.0) is False
        assert await service.evaluate_condition(AlertCondition.NOT_EQUALS, 10.1, 10.0) is True

    @pytest.mark.asyncio
    async def test_evaluate_greater_than(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN, 11.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN, 10.0, 10.0) is False
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN, 9.0, 10.0) is False

    @pytest.mark.asyncio
    async def test_evaluate_less_than(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.LESS_THAN, 9.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.LESS_THAN, 10.0, 10.0) is False

    @pytest.mark.asyncio
    async def test_evaluate_greater_than_or_equal(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN_OR_EQUAL, 10.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN_OR_EQUAL, 11.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.GREATER_THAN_OR_EQUAL, 9.0, 10.0) is False

    @pytest.mark.asyncio
    async def test_evaluate_less_than_or_equal(self):
        db = MagicMock()
        service = AlertService(db)
        assert await service.evaluate_condition(AlertCondition.LESS_THAN_OR_EQUAL, 10.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.LESS_THAN_OR_EQUAL, 9.0, 10.0) is True
        assert await service.evaluate_condition(AlertCondition.LESS_THAN_OR_EQUAL, 11.0, 10.0) is False


class TestAlertServiceCheckTrigger:
    @pytest.mark.asyncio
    async def test_check_and_trigger_no_rules(self):
        db = MagicMock()
        service = AlertService(db)

        with patch.object(service, "list_rules", return_value=[]):
            events = await service.check_and_trigger("cpu_usage", 95.0)
            assert events == []

    @pytest.mark.asyncio
    async def test_check_and_trigger_disabled_rule(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=False,
        )

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert") as mock_trigger:
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert events == []
                mock_trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_trigger_wrong_metric(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="memory_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=True,
        )

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert") as mock_trigger:
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert events == []
                mock_trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_trigger_cooldown_active(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=True,
            cooldown_seconds=300,
            last_triggered_at=datetime.now(timezone.utc) - timedelta(seconds=100),
        )

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert") as mock_trigger:
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert events == []
                mock_trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_trigger_condition_met(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=True,
        )

        mock_event = MagicMock()

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert", return_value=mock_event) as mock_trigger:
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert len(events) == 1
                assert events[0] == mock_event
                mock_trigger.assert_called_once_with(rule, 95.0)

    @pytest.mark.asyncio
    async def test_check_and_trigger_condition_not_met(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=True,
        )

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert") as mock_trigger:
                events = await service.check_and_trigger("cpu_usage", 75.0)
                assert events == []
                mock_trigger.assert_not_called()


class TestAlertServiceEdgeCases:
    @pytest.mark.asyncio
    async def test_multiple_rules_triggered(self):
        db = MagicMock()
        service = AlertService(db)

        rule1 = AlertRule(
            id=uuid4(),
            name="Rule 1",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com/1",
            enabled=True,
        )

        rule2 = AlertRule(
            id=uuid4(),
            name="Rule 2",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=90.0,
            webhook_url="https://example.com/2",
            enabled=True,
        )

        mock_event1 = MagicMock()
        mock_event2 = MagicMock()

        with patch.object(service, "list_rules", return_value=[rule1, rule2]):
            with patch.object(service, "_trigger_alert", side_effect=[mock_event1, mock_event2]):
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert len(events) == 2

    @pytest.mark.asyncio
    async def test_cooldown_expired(self):
        db = MagicMock()
        service = AlertService(db)

        rule = AlertRule(
            id=uuid4(),
            name="Test Rule",
            metric_name="cpu_usage",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            webhook_url="https://example.com",
            enabled=True,
            cooldown_seconds=300,
            last_triggered_at=datetime.now(timezone.utc) - timedelta(seconds=400),
        )

        mock_event = MagicMock()

        with patch.object(service, "list_rules", return_value=[rule]):
            with patch.object(service, "_trigger_alert", return_value=mock_event):
                events = await service.check_and_trigger("cpu_usage", 95.0)
                assert len(events) == 1
