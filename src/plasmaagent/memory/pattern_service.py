import json
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.schema import TaskPattern


class PatternNotFoundError(Exception):
    def __init__(self, pattern_id: UUID):
        super().__init__(f"Task pattern {pattern_id} not found")
        self.pattern_id = pattern_id


class PatternService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def record_pattern(
        self,
        task_name: str,
        commands: list[str],
        user_id: UUID | None = None,
        duration_ms: float = 0.0,
        success: bool = True
    ) -> TaskPattern:
        pattern_id = uuid4()
        now = datetime.now(timezone.utc)
        confidence = 1.0 if success else 0.0
        success_count = 1 if success else 0

        pattern = TaskPattern(
            id=pattern_id,
            user_id=user_id,
            task_name=task_name,
            commands=json.dumps(commands),
            success_count=success_count,
            avg_duration_ms=duration_ms,
            confidence=confidence,
            created_at=now,
            updated_at=now
        )
        self._session.add(pattern)
        await self._session.commit()

        return pattern

    async def get_pattern(self, pattern_id: UUID) -> TaskPattern:
        stmt = select(TaskPattern).where(TaskPattern.id == pattern_id)
        result = await self._session.execute(stmt)
        pattern = result.scalar_one_or_none()

        if not pattern:
            raise PatternNotFoundError(pattern_id)

        return pattern

    async def find_by_task_name(
        self,
        task_name: str,
        user_id: UUID | None = None,
        limit: int = 10
    ) -> list[TaskPattern]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not task_name or len(task_name) > 200:
            raise ValueError("task_name must be 1-200 characters")

        stmt = select(TaskPattern).where(
            TaskPattern.task_name.ilike(f"%{task_name}%")
        )

        if user_id:
            stmt = stmt.where(TaskPattern.user_id == user_id)

        stmt = stmt.order_by(
            TaskPattern.confidence.desc(),
            TaskPattern.updated_at.desc()
        ).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_success(
        self,
        pattern_id: UUID,
        duration_ms: float,
        success: bool = True
    ) -> TaskPattern:
        now = datetime.now(timezone.utc)

        stmt = select(TaskPattern).where(TaskPattern.id == pattern_id)
        result = await self._session.execute(stmt)
        pattern = result.scalar_one_or_none()

        if not pattern:
            raise PatternNotFoundError(pattern_id)

        old_count = pattern.success_count
        old_avg = pattern.avg_duration_ms
        new_count = old_count + (1 if success else 0)
        total_runs = old_count + 1
        new_avg = ((old_avg * old_count) + duration_ms) / total_runs if total_runs > 0 else duration_ms
        new_confidence = new_count / total_runs if total_runs > 0 else 0.0

        pattern.success_count = new_count
        pattern.avg_duration_ms = new_avg
        pattern.confidence = new_confidence
        pattern.updated_at = now

        await self._session.commit()
        return pattern

    async def delete_pattern(self, pattern_id: UUID) -> None:
        stmt = delete(TaskPattern).where(TaskPattern.id == pattern_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        
        if result.rowcount == 0:
            raise PatternNotFoundError(pattern_id)

    async def get_top_patterns(
        self,
        user_id: UUID | None = None,
        limit: int = 20
    ) -> list[TaskPattern]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        stmt = select(TaskPattern)

        if user_id:
            stmt = stmt.where(TaskPattern.user_id == user_id)

        stmt = stmt.order_by(
            TaskPattern.confidence.desc(),
            TaskPattern.success_count.desc()
        ).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
