from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.database import Database, get_database
from plasmaagent.core.schema import TemplateMetric
from plasmaagent.models.template_metrics import (
    TemplateMetrics,
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)


class TemplateMetricsService:
    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or get_database()

    async def create_metric(self, data: TemplateMetricsCreate) -> TemplateMetrics:
        metric_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        async with self._db.transaction() as session:
            metric = TemplateMetric(
                id=metric_id,
                template_name=data.template_name,
                pattern=data.pattern,
                usage_count=data.usage_count,
                success_count=data.success_count,
                failure_count=data.failure_count,
                avg_confidence=float(data.avg_confidence),
                total_generation_time_ms=data.total_generation_time_ms,
                last_used_at=data.last_used_at,
                created_at=now,
                updated_at=now,
            )
            session.add(metric)
            await session.commit()
            
            return TemplateMetrics(
                id=UUID(metric_id),
                template_name=metric.template_name,
                pattern=metric.pattern,
                usage_count=metric.usage_count,
                success_count=metric.success_count,
                failure_count=metric.failure_count,
                avg_confidence=Decimal(str(metric.avg_confidence)),
                total_generation_time_ms=metric.total_generation_time_ms,
                last_used_at=metric.last_used_at,
                created_at=metric.created_at,
                updated_at=metric.updated_at,
            )

    async def get_by_name(self, template_name: str) -> Optional[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = select(TemplateMetric).where(
                TemplateMetric.template_name == template_name
            ).limit(1)
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if metric is None:
                return None
            
            return self._to_model(metric)

    async def get_by_name_and_pattern(
        self,
        template_name: str,
        pattern: str,
    ) -> Optional[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = select(TemplateMetric).where(
                TemplateMetric.template_name == template_name,
                TemplateMetric.pattern == pattern,
            )
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if metric is None:
                return None
            
            return self._to_model(metric)

    async def get_by_id(self, metric_id: UUID) -> Optional[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = select(TemplateMetric).where(
                TemplateMetric.id == str(metric_id)
            )
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if metric is None:
                return None
            
            return self._to_model(metric)

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

        async with self._db.transaction() as session:
            stmt = select(TemplateMetric).where(
                TemplateMetric.template_name == template_name,
                TemplateMetric.pattern == pattern,
            )
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if metric is None:
                metric_id = str(uuid4())
                metric = TemplateMetric(
                    id=metric_id,
                    template_name=template_name,
                    pattern=pattern,
                    usage_count=1,
                    success_count=success_delta,
                    failure_count=failure_delta,
                    avg_confidence=float(confidence),
                    total_generation_time_ms=generation_time_ms,
                    last_used_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(metric)
            else:
                total_usage = metric.usage_count + 1
                metric.usage_count = total_usage
                metric.success_count += success_delta
                metric.failure_count += failure_delta
                metric.avg_confidence = (
                    (metric.avg_confidence * metric.usage_count) + float(confidence)
                ) / total_usage
                metric.total_generation_time_ms += generation_time_ms
                metric.last_used_at = now
                metric.updated_at = now
            
            await session.commit()
            return self._to_model(metric)

    async def update_metric(
        self,
        metric_id: UUID,
        update_data: TemplateMetricsUpdate,
    ) -> Optional[TemplateMetrics]:
        data = update_data.model_dump(exclude_none=True)
        if not data:
            return await self.get_by_id(metric_id)

        async with self._db.transaction() as session:
            stmt = select(TemplateMetric).where(
                TemplateMetric.id == str(metric_id)
            )
            result = await session.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if metric is None:
                return None
            
            for field, value in data.items():
                if hasattr(metric, field):
                    setattr(metric, field, float(value) if isinstance(value, Decimal) else value)
            
            metric.updated_at = datetime.now(timezone.utc)
            await session.commit()
            
            return self._to_model(metric)

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = (
                select(TemplateMetric)
                .order_by(TemplateMetric.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            metrics = result.scalars().all()
            return [self._to_model(m) for m in metrics]

    async def get_top_by_usage(self, limit: int = 10) -> list[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = (
                select(TemplateMetric)
                .where(TemplateMetric.usage_count > 0)
                .order_by(TemplateMetric.usage_count.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            metrics = result.scalars().all()
            return [self._to_model(m) for m in metrics]

    async def get_top_by_success_rate(self, limit: int = 10) -> list[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = (
                select(TemplateMetric)
                .where(TemplateMetric.usage_count > 0)
                .order_by(TemplateMetric.success_count.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            metrics = result.scalars().all()
            return [self._to_model(m) for m in metrics]

    async def get_low_performing(
        self,
        min_usage: int = 5,
        max_success_rate: float = 0.5,
    ) -> list[TemplateMetrics]:
        async with self._db.session() as session:
            stmt = (
                select(TemplateMetric)
                .where(TemplateMetric.usage_count >= min_usage)
                .order_by(TemplateMetric.success_count.asc())
                .limit(100)
            )
            result = await session.execute(stmt)
            metrics = result.scalars().all()
            return [self._to_model(m) for m in metrics]

    async def delete_metric(self, metric_id: UUID) -> bool:
        async with self._db.transaction() as session:
            stmt = delete(TemplateMetric).where(
                TemplateMetric.id == str(metric_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def delete_by_name(self, template_name: str) -> int:
        async with self._db.transaction() as session:
            stmt = delete(TemplateMetric).where(
                TemplateMetric.template_name == template_name
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def delete_by_name_and_pattern(
        self,
        template_name: str,
        pattern: str,
    ) -> bool:
        async with self._db.transaction() as session:
            stmt = delete(TemplateMetric).where(
                TemplateMetric.template_name == template_name,
                TemplateMetric.pattern == pattern,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def get_aggregate_stats(self) -> dict[str, Any]:
        async with self._db.session() as session:
            stmt = select(
                func.count(TemplateMetric.id).label("total_templates"),
                func.coalesce(func.sum(TemplateMetric.usage_count), 0).label("total_usage"),
                func.coalesce(func.sum(TemplateMetric.success_count), 0).label("total_success"),
                func.coalesce(func.sum(TemplateMetric.failure_count), 0).label("total_failure"),
                func.coalesce(func.avg(TemplateMetric.avg_confidence), 0).label("global_avg_confidence"),
                func.coalesce(func.avg(TemplateMetric.total_generation_time_ms), 0).label("avg_generation_time_ms"),
            )
            result = await session.execute(stmt)
            row = result.one()
            
            return {
                "total_templates": int(row.total_templates),
                "total_usage": int(row.total_usage),
                "total_success": int(row.total_success),
                "total_failure": int(row.total_failure),
                "global_avg_confidence": Decimal(str(row.global_avg_confidence)),
                "avg_generation_time_ms": float(row.avg_generation_time_ms),
            }

    def _to_model(self, metric: TemplateMetric) -> TemplateMetrics:
        return TemplateMetrics(
            id=UUID(metric.id),
            template_name=metric.template_name,
            pattern=metric.pattern,
            usage_count=metric.usage_count,
            success_count=metric.success_count,
            failure_count=metric.failure_count,
            avg_confidence=Decimal(str(metric.avg_confidence)),
            total_generation_time_ms=metric.total_generation_time_ms,
            last_used_at=metric.last_used_at,
            created_at=metric.created_at,
            updated_at=metric.updated_at,
        )
