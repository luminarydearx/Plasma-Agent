from datetime import datetime
from typing import Any
from uuid import UUID

from plasmaagent.core.database import Database
from plasmaagent.models.task import Task


class OneTimeScheduler:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def schedule_at(
        self,
        task_id: UUID,
        run_at: datetime,
        timezone: str | None = None,
    ) -> Task | None:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=None)

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE tasks
                    SET next_run_at = %s,
                        is_scheduled = true,
                        schedule_timezone = %s,
                        missed_run_policy = 'run_once',
                        cron_expression = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    (run_at, timezone, task_id),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def schedule_in(
        self,
        task_id: UUID,
        seconds: int,
        timezone: str | None = None,
    ) -> Task | None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")

        run_at = datetime.now() + __import__("datetime").timedelta(seconds=seconds)
        return await self.schedule_at(task_id, run_at, timezone)

    async def get_pending_one_time_tasks(self, now: datetime) -> list[Task]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, name, description, status, payload,
                           cron_expression, is_scheduled, next_run_at,
                           last_run_at, schedule_timezone, missed_run_policy,
                           created_at, updated_at
                    FROM tasks
                    WHERE is_scheduled = true
                      AND cron_expression IS NULL
                      AND missed_run_policy = 'run_once'
                      AND next_run_at <= %s
                      AND status IN ('PENDING', 'COMPLETED', 'FAILED')
                    ORDER BY next_run_at ASC
                    LIMIT 100
                    """,
                    (now,),
                )
                rows = await cur.fetchall()

                return [Task(**row) for row in rows]

    async def mark_completed(self, task_id: UUID, executed_at: datetime) -> Task | None:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE tasks
                    SET last_run_at = %s,
                        next_run_at = NULL,
                        is_scheduled = false,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    (executed_at, task_id),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def cancel_schedule(self, task_id: UUID) -> Task | None:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE tasks
                    SET is_scheduled = false,
                        next_run_at = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    (task_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def reschedule(
        self,
        task_id: UUID,
        new_run_at: datetime,
        timezone: str | None = None,
    ) -> Task | None:
        return await self.schedule_at(task_id, new_run_at, timezone)
