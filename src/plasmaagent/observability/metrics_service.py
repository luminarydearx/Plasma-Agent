import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func, case, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.database import Database, get_database
from plasmaagent.core.schema import Task, TaskStep, ExecutionLog, TemplateMetric
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

        async with self._db.session() as session:
            stmt = select(TaskStep).where(
                TaskStep.finished_at.isnot(None),
                TaskStep.duration_ms.isnot(None),
            )

            if start_time is not None:
                stmt = stmt.where(TaskStep.finished_at >= start_time)
            if end_time is not None:
                stmt = stmt.where(TaskStep.finished_at <= end_time)
            if query.task_id is not None:
                stmt = stmt.where(TaskStep.task_id == str(query.task_id))

            result = await session.execute(stmt)
            steps = result.scalars().all()

            if not steps:
                return ExecutionMetrics()

            total = len(steps)
            successful = sum(1 for s in steps if s.status == "COMPLETED")
            failed = sum(1 for s in steps if s.status == "FAILED")
            success_rate = (successful / total) if total > 0 else 0.0

            durations = [s.duration_ms for s in steps if s.duration_ms is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            min_duration = min(durations) if durations else 0
            max_duration = max(durations) if durations else 0

            sorted_durations = sorted(durations)
            p50_duration = sorted_durations[len(sorted_durations) // 2] if sorted_durations else 0
            p95_duration = sorted_durations[int(len(sorted_durations) * 0.95)] if sorted_durations else 0
            p99_duration = sorted_durations[int(len(sorted_durations) * 0.99)] if sorted_durations else 0

            first_finished = min(s.finished_at for s in steps if s.finished_at)
            last_finished = max(s.finished_at for s in steps if s.finished_at)

            throughput = 0.0
            if total > 0 and first_finished and last_finished:
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
                avg_duration_ms=round(float(avg_duration), 2),
                min_duration_ms=float(min_duration),
                max_duration_ms=float(max_duration),
                p50_duration_ms=round(float(p50_duration), 2),
                p95_duration_ms=round(float(p95_duration), 2),
                p99_duration_ms=round(float(p99_duration), 2),
                throughput_per_minute=round(throughput, 4),
            )

    async def get_task_metrics(
        self,
        task_id: UUID,
        query: Optional[MetricsQuery] = None,
    ) -> Optional[TaskMetrics]:
        query = query or MetricsQuery()

        async with self._db.session() as session:
            stmt = select(Task).where(Task.id == str(task_id))
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if task is None:
                return None

            task_name = task.name

            stmt = select(TemplateMetric).where(TemplateMetric.template_name == task_name).limit(1)
            result = await session.execute(stmt)
            template_metric = result.scalar_one_or_none()
            template_name = task_name if template_metric else None

            stmt = select(TaskStep).where(
                TaskStep.task_id == str(task_id),
                TaskStep.finished_at.isnot(None),
            )
            result = await session.execute(stmt)
            steps = result.scalars().all()

            first_exec = None
            last_exec = None
            if steps:
                first_exec = min(s.finished_at for s in steps if s.finished_at)
                last_exec = max(s.finished_at for s in steps if s.finished_at)

            task_query = MetricsQuery(
                time_range=query.time_range,
                task_id=task_id,
                start_time=query.start_time,
                end_time=query.end_time,
            )

        execution = await self.get_execution_metrics(task_query)

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

        async with self._db.session() as session:
            stmt = select(
                func.count(Task.id).label("total"),
                func.sum(case((Task.status == "COMPLETED", 1), else_=0)).label("completed"),
                func.sum(case((Task.status == "FAILED", 1), else_=0)).label("failed"),
                func.sum(case((Task.status == "PENDING", 1), else_=0)).label("pending"),
                func.sum(case((Task.status == "RUNNING", 1), else_=0)).label("running"),
                func.sum(case((Task.status == "CANCELLED", 1), else_=0)).label("cancelled"),
            )
            result = await session.execute(stmt)
            row = result.one()

            task_counts = {
                "total": int(row.total or 0),
                "completed": int(row.completed or 0),
                "failed": int(row.failed or 0),
                "pending": int(row.pending or 0),
                "running": int(row.running or 0),
                "cancelled": int(row.cancelled or 0),
            }

            stmt = select(func.count(func.distinct(TemplateMetric.template_name)))
            result = await session.execute(stmt)
            unique_templates = result.scalar() or 0

        execution = await self.get_execution_metrics(query)
        top_templates = await self.get_top_templates(limit=5)
        failure_patterns = await self.get_failure_patterns(limit=5)

        elapsed = (time.perf_counter() - start) * 1000.0

        total = task_counts["total"]
        completed = task_counts["completed"]
        failed = task_counts["failed"]
        pending = task_counts["pending"]
        running = task_counts["running"]
        cancelled = task_counts["cancelled"]
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
            unique_templates_used=int(unique_templates),
            top_templates=top_templates,
            failure_patterns=failure_patterns,
            query_time_ms=round(elapsed, 2),
        )

    async def get_top_templates(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            stmt = (
                select(
                    TemplateMetric.template_name,
                    func.count(TemplateMetric.id).label("usage_count"),
                    func.sum(case((TemplateMetric.success_count > 0, 1), else_=0)).label("success_count"),
                    func.sum(TemplateMetric.failure_count).label("failure_count"),
                    func.avg(TemplateMetric.avg_confidence).label("avg_confidence"),
                )
                .where(TemplateMetric.usage_count > 0)
                .group_by(TemplateMetric.template_name)
                .order_by(func.count(TemplateMetric.id).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "template_name": str(row.template_name),
                    "usage_count": int(row.usage_count),
                    "success_count": int(row.success_count or 0),
                    "failure_count": int(row.failure_count or 0),
                    "avg_confidence": float(row.avg_confidence or 0),
                    "success_rate": round(float(row.success_count or 0) / float(row.usage_count), 4) if row.usage_count > 0 else 0.0,
                }
                for row in rows
            ]

    async def get_failure_patterns(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            stmt = (
                select(
                    ExecutionLog.message,
                    func.count(ExecutionLog.id).label("occurrences"),
                    func.count(func.distinct(ExecutionLog.task_id)).label("affected_tasks"),
                    func.max(ExecutionLog.timestamp).label("last_occurred"),
                )
                .where(ExecutionLog.log_level == "ERROR")
                .group_by(ExecutionLog.message)
                .order_by(func.count(ExecutionLog.id).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "message": str(row.message),
                    "occurrences": int(row.occurrences),
                    "affected_tasks": int(row.affected_tasks),
                    "last_occurred": row.last_occurred,
                }
                for row in rows
            ]

    async def get_active_task_count(self) -> int:
        async with self._db.session() as session:
            stmt = select(func.count(Task.id)).where(Task.status.in_(["PENDING", "RUNNING"]))
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_tasks_by_status(self, status: str) -> int:
        async with self._db.session() as session:
            stmt = select(func.count(Task.id)).where(Task.status == status)
            result = await session.execute(stmt)
            return result.scalar() or 0
