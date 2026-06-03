import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from psycopg.rows import dict_row

from plasmaagent.core.database import Database, get_database
from plasmaagent.observability.models import (
    ExecutionMetrics,
    MetricsQuery,
    SystemMetrics,
    TaskMetrics,
    TimeRange,
)


class MetricsAggregationService:
    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or get_database()

    async def get_execution_metrics(
        self,
        query: Optional[MetricsQuery] = None,
    ) -> ExecutionMetrics:
        query = query or MetricsQuery()
        start_time, end_time = query.get_time_bounds()

        where_clauses: list[str] = []
        params: list[Any] = []

        if start_time is not None:
            where_clauses.append("ts.finished_at >= %s")
            params.append(start_time)
        if end_time is not None:
            where_clauses.append("ts.finished_at <= %s")
            params.append(end_time)
        if query.task_id is not None:
            where_clauses.append("ts.task_id = %s")
            params.append(query.task_id)
        where_clauses.append("ts.finished_at IS NOT NULL")
        where_clauses.append("ts.duration_ms IS NOT NULL")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                COUNT(*) AS total_executions,
                COUNT(*) FILTER (WHERE ts.status = 'COMPLETED') AS successful,
                COUNT(*) FILTER (WHERE ts.status = 'FAILED') AS failed,
                COALESCE(AVG(ts.duration_ms), 0) AS avg_duration,
                COALESCE(MIN(ts.duration_ms), 0) AS min_duration,
                COALESCE(MAX(ts.duration_ms), 0) AS max_duration,
                COALESCE(
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ts.duration_ms),
                    0
                ) AS p50_duration,
                COALESCE(
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ts.duration_ms),
                    0
                ) AS p95_duration,
                COALESCE(
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ts.duration_ms),
                    0
                ) AS p99_duration,
                MIN(ts.finished_at) AS first_finished,
                MAX(ts.finished_at) AS last_finished
            FROM task_steps ts
            WHERE {where_sql}
        """

        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, tuple(params))
                row = await cur.fetchone()
                if row is None:
                    return ExecutionMetrics()

                total = int(row["total_executions"])
                successful = int(row["successful"])
                failed = int(row["failed"])
                success_rate = (successful / total) if total > 0 else 0.0

                throughput = 0.0
                if total > 0:
                    first_finished = row["first_finished"]
                    last_finished = row["last_finished"]
                    if first_finished and last_finished:
                        span_seconds = (last_finished - first_finished).total_seconds()
                        if span_seconds > 0:
                            throughput = (total / span_seconds) * 60.0
                        else:
                            throughput = float(total)

                return ExecutionMetrics(
                    total_executions=total,
                    successful_executions=successful,
                    failed_executions=failed,
                    success_rate=round(success_rate, 4),
                    avg_duration_ms=round(float(row["avg_duration"]), 2),
                    min_duration_ms=float(row["min_duration"]),
                    max_duration_ms=float(row["max_duration"]),
                    p50_duration_ms=round(float(row["p50_duration"]), 2),
                    p95_duration_ms=round(float(row["p95_duration"]), 2),
                    p99_duration_ms=round(float(row["p99_duration"]), 2),
                    throughput_per_minute=round(throughput, 4),
                )

    async def get_task_metrics(
        self,
        task_id: UUID,
        query: Optional[MetricsQuery] = None,
    ) -> Optional[TaskMetrics]:
        query = query or MetricsQuery()

        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT id, name, created_at FROM tasks WHERE id = %s",
                    (task_id,),
                )
                task_row = await cur.fetchone()
                if task_row is None:
                    return None

                task_name = str(task_row["name"])

                await cur.execute(
                    """SELECT template_name
                       FROM template_metrics
                       WHERE template_name = %s
                       LIMIT 1""",
                    (task_name,),
                )
                template_row = await cur.fetchone()
                template_name = (
                    str(template_row["template_name"])
                    if template_row is not None
                    else None
                )

                await cur.execute(
                    """SELECT MIN(finished_at) AS first_exec,
                              MAX(finished_at) AS last_exec
                       FROM task_steps
                       WHERE task_id = %s AND finished_at IS NOT NULL""",
                    (task_id,),
                )
                time_row = await cur.fetchone()

                task_query = MetricsQuery(
                    time_range=query.time_range,
                    task_id=task_id,
                    start_time=query.start_time,
                    end_time=query.end_time,
                )

        execution = await self.get_execution_metrics(task_query)

        first_exec = None
        last_exec = None
        if time_row is not None:
            first_exec = time_row["first_exec"]
            last_exec = time_row["last_exec"]

        return TaskMetrics(
            task_id=task_id,
            task_name=task_name,
            template_name=template_name,
            execution=execution,
            first_executed_at=first_exec,
            last_executed_at=last_exec,
        )

    async def get_system_metrics(
        self,
        query: Optional[MetricsQuery] = None,
    ) -> SystemMetrics:
        start = time.perf_counter()
        query = query or MetricsQuery()

        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT
                         COUNT(*) AS total,
                         COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
                         COUNT(*) FILTER (WHERE status = 'FAILED') AS failed,
                         COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
                         COUNT(*) FILTER (WHERE status = 'RUNNING') AS running,
                         COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled
                       FROM tasks"""
                )
                task_counts = await cur.fetchone()
                if task_counts is None:
                    task_counts = {
                        "total": 0,
                        "completed": 0,
                        "failed": 0,
                        "pending": 0,
                        "running": 0,
                        "cancelled": 0,
                    }

                await cur.execute(
                    "SELECT COUNT(DISTINCT template_name) AS cnt FROM template_metrics"
                )
                templates_row = await cur.fetchone()
                unique_templates = (
                    int(templates_row["cnt"])
                    if templates_row and templates_row["cnt"] is not None
                    else 0
                )

        execution = await self.get_execution_metrics(query)
        top_templates = await self.get_top_templates(limit=5)
        failure_patterns = await self.get_failure_patterns(limit=5)

        elapsed = (time.perf_counter() - start) * 1000.0

        total = int(task_counts["total"])
        completed = int(task_counts["completed"])
        failed = int(task_counts["failed"])
        pending = int(task_counts["pending"])
        running = int(task_counts["running"])
        cancelled = int(task_counts["cancelled"])
        active = running + pending

        return SystemMetrics(
            total_tasks=total,
            active_tasks=active,
            completed_tasks=completed,
            failed_tasks=failed,
            pending_tasks=pending,
            running_tasks=running,
            cancelled_tasks=cancelled,
            overall_execution=execution,
            unique_templates_used=unique_templates,
            top_templates=top_templates,
            failure_patterns=failure_patterns,
            query_time_ms=round(elapsed, 2),
        )

    async def get_top_templates(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT
                         template_name,
                         usage_count,
                         success_count,
                         failure_count,
                         ROUND(avg_confidence, 4) AS avg_confidence,
                         CASE WHEN usage_count > 0
                              THEN ROUND(
                                  (success_count::numeric / usage_count::numeric), 4
                              )
                              ELSE 0
                         END AS success_rate
                       FROM template_metrics
                       WHERE usage_count > 0
                       ORDER BY usage_count DESC
                       LIMIT %s""",
                    (limit,),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "template_name": str(row["template_name"]),
                        "usage_count": int(row["usage_count"]),
                        "success_count": int(row["success_count"]),
                        "failure_count": int(row["failure_count"]),
                        "avg_confidence": float(row["avg_confidence"]),
                        "success_rate": float(row["success_rate"]),
                    }
                    for row in rows
                ]

    async def get_failure_patterns(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT
                         el.message,
                         COUNT(*) AS occurrences,
                         COUNT(DISTINCT el.task_id) AS affected_tasks,
                         MAX(el.timestamp) AS last_occurred
                       FROM execution_logs el
                       WHERE el.log_level = 'ERROR'
                       GROUP BY el.message
                       ORDER BY occurrences DESC
                       LIMIT %s""",
                    (limit,),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "message": str(row["message"]),
                        "occurrences": int(row["occurrences"]),
                        "affected_tasks": int(row["affected_tasks"]),
                        "last_occurred": row["last_occurred"],
                    }
                    for row in rows
                ]

    async def get_active_task_count(self) -> int:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT COUNT(*) AS cnt
                       FROM tasks
                       WHERE status IN ('PENDING', 'RUNNING')"""
                )
                row = await cur.fetchone()
                return int(row["cnt"]) if row and row["cnt"] is not None else 0

    async def get_tasks_by_status(self, status: str) -> int:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT COUNT(*) AS cnt FROM tasks WHERE status = %s",
                    (status,),
                )
                row = await cur.fetchone()
                return int(row["cnt"]) if row and row["cnt"] is not None else 0
