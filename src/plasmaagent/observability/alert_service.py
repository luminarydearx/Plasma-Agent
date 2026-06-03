from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import httpx
from psycopg.errors import UniqueViolation

from plasmaagent.observability.alert_models import (
    AlertCondition,
    AlertEvent,
    AlertRule,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSeverity,
    AlertStatus,
)

if TYPE_CHECKING:
    from plasmaagent.core.database import Database


class DuplicateAlertRuleError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Alert rule with name '{name}' already exists")


class AlertService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_rule(self, rule_data: AlertRuleCreate) -> AlertRule:
        new_id = uuid4()
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(
                        """INSERT INTO alert_rules
                           (id, name, description, metric_name, condition, threshold, severity,
                            webhook_url, enabled, cooldown_seconds, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING created_at, updated_at""",
                        (
                            new_id,
                            rule_data.name,
                            rule_data.description,
                            rule_data.metric_name,
                            rule_data.condition.value,
                            rule_data.threshold,
                            rule_data.severity.value,
                            rule_data.webhook_url,
                            rule_data.enabled,
                            rule_data.cooldown_seconds,
                            AlertStatus.ACTIVE.value,
                        ),
                    )
                except UniqueViolation:
                    raise DuplicateAlertRuleError(rule_data.name)

                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("Failed to create alert rule")

                return AlertRule(
                    id=new_id,
                    name=rule_data.name,
                    description=rule_data.description,
                    metric_name=rule_data.metric_name,
                    condition=rule_data.condition,
                    threshold=rule_data.threshold,
                    severity=rule_data.severity,
                    webhook_url=rule_data.webhook_url,
                    enabled=rule_data.enabled,
                    cooldown_seconds=rule_data.cooldown_seconds,
                    status=AlertStatus.ACTIVE,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

    async def get_rule(self, rule_id: UUID) -> AlertRule | None:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, name, description, metric_name, condition, threshold,
                              severity, webhook_url, enabled, cooldown_seconds, status,
                              last_triggered_at, created_at, updated_at
                       FROM alert_rules WHERE id = %s""",
                    (rule_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    return None

                return AlertRule(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    metric_name=row["metric_name"],
                    condition=AlertCondition(row["condition"]),
                    threshold=row["threshold"],
                    severity=AlertSeverity(row["severity"]),
                    webhook_url=row["webhook_url"],
                    enabled=row["enabled"],
                    cooldown_seconds=row["cooldown_seconds"],
                    status=AlertStatus(row["status"]),
                    last_triggered_at=row["last_triggered_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

    async def list_rules(self, limit: int = 100, offset: int = 0) -> list[AlertRule]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, name, description, metric_name, condition, threshold,
                              severity, webhook_url, enabled, cooldown_seconds, status,
                              last_triggered_at, created_at, updated_at
                       FROM alert_rules ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
                rows = await cur.fetchall()

                return [
                    AlertRule(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        metric_name=row["metric_name"],
                        condition=AlertCondition(row["condition"]),
                        threshold=row["threshold"],
                        severity=AlertSeverity(row["severity"]),
                        webhook_url=row["webhook_url"],
                        enabled=row["enabled"],
                        cooldown_seconds=row["cooldown_seconds"],
                        status=AlertStatus(row["status"]),
                        last_triggered_at=row["last_triggered_at"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    for row in rows
                ]

    async def update_rule(self, rule_id: UUID, update: AlertRuleUpdate) -> AlertRule | None:
        existing = await self.get_rule(rule_id)
        if existing is None:
            return None

        updates = []
        values = []
        if update.name is not None:
            updates.append("name = %s")
            values.append(update.name)
        if update.description is not None:
            updates.append("description = %s")
            values.append(update.description)
        if update.threshold is not None:
            updates.append("threshold = %s")
            values.append(update.threshold)
        if update.severity is not None:
            updates.append("severity = %s")
            values.append(update.severity.value)
        if update.webhook_url is not None:
            updates.append("webhook_url = %s")
            values.append(update.webhook_url)
        if update.enabled is not None:
            updates.append("enabled = %s")
            values.append(update.enabled)
        if update.cooldown_seconds is not None:
            updates.append("cooldown_seconds = %s")
            values.append(update.cooldown_seconds)

        if not updates:
            return existing

        updates.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(rule_id)

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE alert_rules SET {', '.join(updates)} WHERE id = %s",
                    values,
                )

        return await self.get_rule(rule_id)

    async def delete_rule(self, rule_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM alert_rules WHERE id = %s", (rule_id,))
                return cur.rowcount > 0

    async def delete_rule_by_name(self, name: str) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM alert_rules WHERE name = %s", (name,))
                return cur.rowcount > 0

    async def evaluate_condition(self, condition: AlertCondition, value: float, threshold: float) -> bool:
        if condition == AlertCondition.EQUALS:
            return abs(value - threshold) < 0.0001
        elif condition == AlertCondition.NOT_EQUALS:
            return abs(value - threshold) >= 0.0001
        elif condition == AlertCondition.GREATER_THAN:
            return value > threshold
        elif condition == AlertCondition.LESS_THAN:
            return value < threshold
        elif condition == AlertCondition.GREATER_THAN_OR_EQUAL:
            return value >= threshold
        elif condition == AlertCondition.LESS_THAN_OR_EQUAL:
            return value <= threshold
        else:
            return False

    async def check_and_trigger(self, metric_name: str, metric_value: float) -> list[AlertEvent]:
        rules = await self.list_rules()
        triggered_events = []

        for rule in rules:
            if not rule.enabled or rule.status == AlertStatus.DISABLED:
                continue

            if rule.metric_name != metric_name:
                continue

            if rule.last_triggered_at is not None:
                now = datetime.now(timezone.utc)
                elapsed = (now - rule.last_triggered_at).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            condition_met = await self.evaluate_condition(rule.condition, metric_value, rule.threshold)

            if condition_met:
                event = await self._trigger_alert(rule, metric_value)
                triggered_events.append(event)

        return triggered_events

    async def _trigger_alert(self, rule: AlertRule, metric_value: float) -> AlertEvent:
        message = (
            f"Alert: {rule.name} - {rule.metric_name} {rule.condition.value} {rule.threshold} "
            f"(actual: {metric_value})"
        )

        webhook_status = "pending"
        webhook_response = None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    rule.webhook_url,
                    json={
                        "rule_id": str(rule.id),
                        "rule_name": rule.name,
                        "severity": rule.severity.value,
                        "metric_name": rule.metric_name,
                        "metric_value": metric_value,
                        "threshold": rule.threshold,
                        "condition": rule.condition.value,
                        "message": message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                webhook_status = "success" if response.status_code < 400 else "failed"
                webhook_response = f"Status: {response.status_code}"
        except Exception as e:
            webhook_status = "error"
            webhook_response = str(e)[:500]

        event = AlertEvent(
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            condition=rule.condition,
            message=message,
            webhook_url=rule.webhook_url,
            webhook_status=webhook_status,
            webhook_response=webhook_response,
        )

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO alert_events
                       (id, rule_id, rule_name, severity, metric_name, metric_value,
                        threshold, condition, message, webhook_url, webhook_status,
                        webhook_response, triggered_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        event.id,
                        event.rule_id,
                        event.rule_name,
                        event.severity.value,
                        event.metric_name,
                        event.metric_value,
                        event.threshold,
                        event.condition.value,
                        event.message,
                        event.webhook_url,
                        event.webhook_status,
                        event.webhook_response,
                        event.triggered_at,
                    ),
                )

                await cur.execute(
                    "UPDATE alert_rules SET last_triggered_at = %s, status = %s WHERE id = %s",
                    (datetime.now(timezone.utc), AlertStatus.TRIGGERED.value, rule.id),
                )

        return event

    async def get_recent_events(self, limit: int = 50) -> list[AlertEvent]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, rule_id, rule_name, severity, metric_name, metric_value,
                              threshold, condition, message, webhook_url, webhook_status,
                              webhook_response, triggered_at, resolved_at
                       FROM alert_events ORDER BY triggered_at DESC LIMIT %s""",
                    (limit,),
                )
                rows = await cur.fetchall()

                return [
                    AlertEvent(
                        id=row["id"],
                        rule_id=row["rule_id"],
                        rule_name=row["rule_name"],
                        severity=AlertSeverity(row["severity"]),
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        threshold=row["threshold"],
                        condition=AlertCondition(row["condition"]),
                        message=row["message"],
                        webhook_url=row["webhook_url"],
                        webhook_status=row["webhook_status"],
                        webhook_response=row["webhook_response"],
                        triggered_at=row["triggered_at"],
                        resolved_at=row["resolved_at"],
                    )
                    for row in rows
                ]
