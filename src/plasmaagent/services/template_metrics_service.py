from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from psycopg.rows import dict_row

from plasmaagent.core.database import Database, get_database
from plasmaagent.models.template_metrics import (
    TemplateMetrics,
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)


class TemplateMetricsService:
    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or get_database()

    async def create_metric(self, data: TemplateMetricsCreate) -> TemplateMetrics:
        async with self._db.transaction() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO template_metrics
                       (template_name, pattern, usage_count, success_count,
                        failure_count, avg_confidence, total_generation_time_ms,
                        last_used_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        data.template_name,
                        data.pattern,
                        data.usage_count,
                        data.success_count,
                        data.failure_count,
                        data.avg_confidence,
                        data.total_generation_time_ms,
                        data.last_used_at,
                    ),
                )
                result = await cur.fetchone()
                if result is None:
                    raise ValueError("Failed to create template metric")
                return TemplateMetrics(**result)

    async def get_by_name(self, template_name: str) -> Optional[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM template_metrics WHERE template_name = %s LIMIT 1",
                    (template_name,),
                )
                result = await cur.fetchone()
                if result is None:
                    return None
                return TemplateMetrics(**result)

    async def get_by_name_and_pattern(
        self,
        template_name: str,
        pattern: str,
    ) -> Optional[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM template_metrics
                       WHERE template_name = %s AND pattern = %s""",
                    (template_name, pattern),
                )
                result = await cur.fetchone()
                if result is None:
                    return None
                return TemplateMetrics(**result)

    async def get_by_id(self, metric_id: UUID) -> Optional[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM template_metrics WHERE id = %s",
                    (metric_id,),
                )
                result = await cur.fetchone()
                if result is None:
                    return None
                return TemplateMetrics(**result)

    async def record_usage(
        self,
        template_name: str,
        pattern: str,
        confidence: Decimal,
        generation_time_ms: int,
        success: bool,
    ) -> TemplateMetrics:
        now = datetime.now(timezone.utc)
        success_delta = 1 if success else 0
        failure_delta = 0 if success else 1

        async with self._db.transaction() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO template_metrics
                       (template_name, pattern, usage_count, success_count,
                        failure_count, avg_confidence,
                        total_generation_time_ms, last_used_at)
                       VALUES (%s, %s, 1, %s, %s, %s, %s, %s)
                       ON CONFLICT (template_name, pattern) DO UPDATE
                       SET usage_count = template_metrics.usage_count + 1,
                           success_count = template_metrics.success_count
                               + EXCLUDED.success_count,
                           failure_count = template_metrics.failure_count
                               + EXCLUDED.failure_count,
                           avg_confidence = (
                               (template_metrics.avg_confidence
                                   * template_metrics.usage_count)
                               + EXCLUDED.avg_confidence
                           ) / (template_metrics.usage_count + 1),
                           total_generation_time_ms =
                               template_metrics.total_generation_time_ms
                               + EXCLUDED.total_generation_time_ms,
                           last_used_at = EXCLUDED.last_used_at,
                           updated_at = EXCLUDED.last_used_at
                       RETURNING *""",
                    (
                        template_name,
                        pattern,
                        success_delta,
                        failure_delta,
                        confidence,
                        generation_time_ms,
                        now,
                    ),
                )
                result = await cur.fetchone()
                if result is None:
                    raise ValueError(
                        f"Failed to record usage for {template_name}:{pattern}"
                    )
                return TemplateMetrics(**result)

    async def update_metric(
        self,
        metric_id: UUID,
        update: TemplateMetricsUpdate,
    ) -> Optional[TemplateMetrics]:
        update_data = update.model_dump(exclude_none=True)
        if not update_data:
            return await self.get_by_id(metric_id)

        set_clauses: list[str] = []
        values: list[Any] = []
        for field, value in update_data.items():
            set_clauses.append(f"{field} = %s")
            values.append(value)

        set_clauses.append("updated_at = %s")
        values.append(datetime.now(timezone.utc))
        values.append(metric_id)

        query = f"""UPDATE template_metrics
                    SET {', '.join(set_clauses)}
                    WHERE id = %s
                    RETURNING *"""

        async with self._db.transaction() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, tuple(values))
                result = await cur.fetchone()
                if result is None:
                    return None
                return TemplateMetrics(**result)

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM template_metrics
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
                results = await cur.fetchall()
                return [TemplateMetrics(**row) for row in results]

    async def get_top_by_usage(self, limit: int = 10) -> list[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM template_metrics
                       WHERE usage_count > 0
                       ORDER BY usage_count DESC
                       LIMIT %s""",
                    (limit,),
                )
                results = await cur.fetchall()
                return [TemplateMetrics(**row) for row in results]

    async def get_top_by_success_rate(self, limit: int = 10) -> list[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM template_metrics
                       WHERE usage_count > 0
                       ORDER BY (success_count::float / GREATEST(usage_count, 1)) DESC,
                                usage_count DESC
                       LIMIT %s""",
                    (limit,),
                )
                results = await cur.fetchall()
                return [TemplateMetrics(**row) for row in results]

    async def get_low_performing(
        self,
        min_usage: int = 5,
        max_success_rate: float = 0.5,
    ) -> list[TemplateMetrics]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM template_metrics
                       WHERE usage_count >= %s
                         AND (success_count::float / GREATEST(usage_count, 1)) <= %s
                       ORDER BY (success_count::float / GREATEST(usage_count, 1)) ASC""",
                    (min_usage, max_success_rate),
                )
                results = await cur.fetchall()
                return [TemplateMetrics(**row) for row in results]

    async def delete_metric(self, metric_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM template_metrics WHERE id = %s",
                    (metric_id,),
                )
                return cur.rowcount > 0

    async def delete_by_name(self, template_name: str) -> int:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM template_metrics WHERE template_name = %s",
                    (template_name,),
                )
                return cur.rowcount

    async def delete_by_name_and_pattern(
        self,
        template_name: str,
        pattern: str,
    ) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """DELETE FROM template_metrics
                       WHERE template_name = %s AND pattern = %s""",
                    (template_name, pattern),
                )
                return cur.rowcount > 0

    async def get_aggregate_stats(self) -> dict[str, Any]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT
                         COUNT(*) AS total_templates,
                         COALESCE(SUM(usage_count), 0) AS total_usage,
                         COALESCE(SUM(success_count), 0) AS total_success,
                         COALESCE(SUM(failure_count), 0) AS total_failure,
                         COALESCE(AVG(avg_confidence), 0) AS global_avg_confidence,
                         COALESCE(AVG(total_generation_time_ms), 0)
                             AS avg_generation_time_ms
                       FROM template_metrics"""
                )
                result = await cur.fetchone()
                if result is None:
                    return {
                        "total_templates": 0,
                        "total_usage": 0,
                        "total_success": 0,
                        "total_failure": 0,
                        "global_avg_confidence": Decimal("0.0000"),
                        "avg_generation_time_ms": 0,
                    }
                return {
                    "total_templates": int(result["total_templates"]),
                    "total_usage": int(result["total_usage"]),
                    "total_success": int(result["total_success"]),
                    "total_failure": int(result["total_failure"]),
                    "global_avg_confidence": Decimal(str(result["global_avg_confidence"])),
                    "avg_generation_time_ms": float(result["avg_generation_time_ms"]),
                }
