from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from plasmaagent.core.database import Database


class ExecutionMetricsTracker:
    """Track and analyze execution metrics for self-improvement."""

    EVENT_TYPE = "execution_metric"

    def __init__(self, db: Database, retention_days: int = 30):
        self._db = db
        self._retention_days = retention_days

    async def track_execution(
        self,
        template_name: str,
        success: bool,
        execution_time_ms: int,
        error_message: str | None = None,
        commands: list[str] | None = None,
        task_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "template_name": template_name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error_message": error_message,
            "commands": commands or [],
            "task_id": str(task_id) if task_id else None,
            "metadata": metadata or {},
        }

        async with self._db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO telemetry (event_type, payload)
                VALUES (%s, %s)
                """,
                (self.EVENT_TYPE, Jsonb(payload)),
            )

    async def get_template_stats(self, template_name: str) -> dict[str, Any]:
        async with self._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_executions,
                    COUNT(*) FILTER (WHERE (payload->>'success')::boolean = true) as successful_executions,
                    COUNT(*) FILTER (WHERE (payload->>'success')::boolean = false) as failed_executions,
                    AVG((payload->>'execution_time_ms')::integer) as avg_execution_time_ms,
                    MIN((payload->>'execution_time_ms')::integer) as min_execution_time_ms,
                    MAX((payload->>'execution_time_ms')::integer) as max_execution_time_ms
                FROM telemetry
                WHERE event_type = %s
                  AND payload->>'template_name' = %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                """,
                (self.EVENT_TYPE, template_name, self._retention_days),
            )
            result = await cursor.fetchone()

            if not result or result["total_executions"] == 0:
                return {
                    "template_name": template_name,
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "success_rate": 0.0,
                    "avg_execution_time_ms": 0,
                    "min_execution_time_ms": 0,
                    "max_execution_time_ms": 0,
                }

            success_rate = (
                result["successful_executions"] / result["total_executions"]
                if result["total_executions"] > 0
                else 0.0
            )

            return {
                "template_name": template_name,
                "total_executions": result["total_executions"],
                "successful_executions": result["successful_executions"],
                "failed_executions": result["failed_executions"],
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": int(result["avg_execution_time_ms"] or 0),
                "min_execution_time_ms": result["min_execution_time_ms"] or 0,
                "max_execution_time_ms": result["max_execution_time_ms"] or 0,
            }

    async def get_all_template_stats(self) -> list[dict[str, Any]]:
        async with self._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                SELECT DISTINCT payload->>'template_name' as template_name
                FROM telemetry
                WHERE event_type = %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                """,
                (self.EVENT_TYPE, self._retention_days),
            )
            results = await cursor.fetchall()

            stats = []
            for row in results:
                template_name = row["template_name"]
                if template_name:
                    template_stats = await self.get_template_stats(template_name)
                    stats.append(template_stats)

            return stats

    async def get_failure_patterns(
        self, template_name: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with self._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)

            if template_name:
                await cursor.execute(
                    """
                    SELECT 
                        payload->>'error_message' as error_message,
                        COUNT(*) as occurrence_count,
                        payload->>'template_name' as template_name
                    FROM telemetry
                    WHERE event_type = %s
                      AND (payload->>'success')::boolean = false
                      AND payload->>'template_name' = %s
                      AND payload->>'error_message' IS NOT NULL
                      AND timestamp >= NOW() - INTERVAL '%s days'
                    GROUP BY payload->>'error_message', payload->>'template_name'
                    ORDER BY occurrence_count DESC
                    LIMIT %s
                    """,
                    (self.EVENT_TYPE, template_name, self._retention_days, limit),
                )
            else:
                await cursor.execute(
                    """
                    SELECT 
                        payload->>'error_message' as error_message,
                        COUNT(*) as occurrence_count,
                        payload->>'template_name' as template_name
                    FROM telemetry
                    WHERE event_type = %s
                      AND (payload->>'success')::boolean = false
                      AND payload->>'error_message' IS NOT NULL
                      AND timestamp >= NOW() - INTERVAL '%s days'
                    GROUP BY payload->>'error_message', payload->>'template_name'
                    ORDER BY occurrence_count DESC
                    LIMIT %s
                    """,
                    (self.EVENT_TYPE, self._retention_days, limit),
                )

            results = await cursor.fetchall()
            return [dict(row) for row in results]

    async def get_slow_executions(
        self, threshold_ms: int = 5000, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with self._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                SELECT 
                    payload->>'template_name' as template_name,
                    (payload->>'execution_time_ms')::integer as execution_time_ms,
                    payload->'commands' as commands,
                    timestamp
                FROM telemetry
                WHERE event_type = %s
                  AND (payload->>'execution_time_ms')::integer > %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY (payload->>'execution_time_ms')::integer DESC
                LIMIT %s
                """,
                (self.EVENT_TYPE, threshold_ms, self._retention_days, limit),
            )
            results = await cursor.fetchall()
            return [dict(row) for row in results]

    async def cleanup_old_metrics(self) -> int:
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                DELETE FROM telemetry
                WHERE event_type = %s
                  AND timestamp < NOW() - INTERVAL '%s days'
                """,
                (self.EVENT_TYPE, self._retention_days),
            )
            return cursor.rowcount

    async def get_top_templates(self, limit: int = 5) -> list[dict[str, Any]]:
        all_stats = await self.get_all_template_stats()
        sorted_stats = sorted(
            all_stats, key=lambda x: x["total_executions"], reverse=True
        )
        return sorted_stats[:limit]

    async def get_low_success_rate_templates(
        self, threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        all_stats = await self.get_all_template_stats()
        low_success = [
            stat
            for stat in all_stats
            if stat["success_rate"] < threshold and stat["total_executions"] > 0
        ]
        return sorted(low_success, key=lambda x: x["success_rate"])
