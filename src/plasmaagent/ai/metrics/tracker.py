from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, delete, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.database import Database
from plasmaagent.core.schema import ExecutionLog


class ExecutionMetricsTracker:
    """Track and analyze execution metrics for self-improvement."""

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
        async with self._db.session() as session:
            log = ExecutionLog(
                task_id=task_id,
                status="SUCCESS" if success else "FAILED",
                execution_time_ms=execution_time_ms,
                error_message=error_message,
                commands=commands or [],
                metadata={
                    "template_name": template_name,
                    **(metadata or {}),
                },
            )
            session.add(log)
            await session.commit()

    async def get_template_stats(self, template_name: str) -> dict[str, Any]:
        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
            
            stmt = select(
                func.count(ExecutionLog.id).label("total_executions"),
                func.sum(
                    func.case((ExecutionLog.status == "SUCCESS", 1), else_=0)
                ).label("successful_executions"),
                func.sum(
                    func.case((ExecutionLog.status == "FAILED", 1), else_=0)
                ).label("failed_executions"),
                func.avg(ExecutionLog.execution_time_ms).label("avg_execution_time_ms"),
                func.min(ExecutionLog.execution_time_ms).label("min_execution_time_ms"),
                func.max(ExecutionLog.execution_time_ms).label("max_execution_time_ms"),
            ).where(
                and_(
                    ExecutionLog.created_at >= cutoff_date,
                    ExecutionLog.metadata["template_name"].as_string() == template_name,
                )
            )
            
            result = await session.execute(stmt)
            row = result.first()
            
            if not row or row.total_executions == 0:
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
                row.successful_executions / row.total_executions
                if row.total_executions > 0
                else 0.0
            )

            return {
                "template_name": template_name,
                "total_executions": row.total_executions,
                "successful_executions": row.successful_executions or 0,
                "failed_executions": row.failed_executions or 0,
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": int(row.avg_execution_time_ms or 0),
                "min_execution_time_ms": row.min_execution_time_ms or 0,
                "max_execution_time_ms": row.max_execution_time_ms or 0,
            }

    async def get_all_template_stats(self) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
            
            stmt = select(
                ExecutionLog.metadata["template_name"].as_string().label("template_name")
            ).where(
                ExecutionLog.created_at >= cutoff_date
            ).distinct()
            
            result = await session.execute(stmt)
            template_names = [row.template_name for row in result if row.template_name]
            
            stats = []
            for template_name in template_names:
                template_stats = await self.get_template_stats(template_name)
                stats.append(template_stats)

            return stats

    async def get_failure_patterns(
        self, template_name: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
            
            conditions = [
                ExecutionLog.status == "FAILED",
                ExecutionLog.created_at >= cutoff_date,
                ExecutionLog.error_message.isnot(None),
            ]
            
            if template_name:
                conditions.append(
                    ExecutionLog.metadata["template_name"].as_string() == template_name
                )
            
            stmt = select(
                ExecutionLog.error_message.label("error_message"),
                func.count(ExecutionLog.id).label("occurrence_count"),
                ExecutionLog.metadata["template_name"].as_string().label("template_name"),
            ).where(
                and_(*conditions)
            ).group_by(
                ExecutionLog.error_message,
                ExecutionLog.metadata["template_name"].as_string(),
            ).order_by(
                func.count(ExecutionLog.id).desc()
            ).limit(limit)
            
            result = await session.execute(stmt)
            return [
                {
                    "error_message": row.error_message,
                    "occurrence_count": row.occurrence_count,
                    "template_name": row.template_name,
                }
                for row in result
            ]

    async def get_slow_executions(
        self, threshold_ms: int = 5000, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
            
            stmt = select(
                ExecutionLog.metadata["template_name"].as_string().label("template_name"),
                ExecutionLog.execution_time_ms,
                ExecutionLog.commands,
                ExecutionLog.created_at.label("timestamp"),
            ).where(
                and_(
                    ExecutionLog.execution_time_ms > threshold_ms,
                    ExecutionLog.created_at >= cutoff_date,
                )
            ).order_by(
                ExecutionLog.execution_time_ms.desc()
            ).limit(limit)
            
            result = await session.execute(stmt)
            return [
                {
                    "template_name": row.template_name,
                    "execution_time_ms": row.execution_time_ms,
                    "commands": row.commands,
                    "timestamp": row.timestamp,
                }
                for row in result
            ]

    async def cleanup_old_metrics(self) -> int:
        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
            
            stmt = delete(ExecutionLog).where(
                ExecutionLog.created_at < cutoff_date
            )
            
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

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
