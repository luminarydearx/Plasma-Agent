from datetime import datetime
from uuid import UUID

from plasmaagent.core.database import Database
from plasmaagent.scheduling.models import (
    MissedRunPolicy,
    TaskScheduleUpdate,
)
from plasmaagent.scheduling.cron_parser import CronParser
from plasmaagent.models.task import Task


class SchedulingService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def enable_schedule(
        self,
        task_id: UUID,
        cron_expression: str,
        timezone: str | None = None,
        missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP,
    ) -> Task | None:
        CronParser.parse(cron_expression)

        cron_expr = CronParser.parse(cron_expression)
        next_run = cron_expr.next_run(datetime.now())

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE tasks
                    SET cron_expression = %s,
                        is_scheduled = true,
                        next_run_at = %s,
                        schedule_timezone = %s,
                        missed_run_policy = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    (
                        cron_expression,
                        next_run,
                        timezone,
                        missed_run_policy.value,
                        task_id,
                    ),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def disable_schedule(self, task_id: UUID) -> Task | None:
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

    async def update_schedule(
        self, task_id: UUID, data: TaskScheduleUpdate
    ) -> Task | None:
        updates = []
        values = []

        if data.cron_expression is not None:
            CronParser.parse(data.cron_expression)
            updates.append("cron_expression = %s")
            values.append(data.cron_expression)

            cron_expr = CronParser.parse(data.cron_expression)
            next_run = cron_expr.next_run(datetime.now())
            updates.append("next_run_at = %s")
            values.append(next_run)

        if data.is_scheduled is not None:
            updates.append("is_scheduled = %s")
            values.append(data.is_scheduled)

        if data.schedule_timezone is not None:
            updates.append("schedule_timezone = %s")
            values.append(data.schedule_timezone)

        if data.missed_run_policy is not None:
            updates.append("missed_run_policy = %s")
            values.append(data.missed_run_policy.value)

        if not updates:
            return await self.get_task(task_id)

        updates.append("updated_at = NOW()")
        values.append(task_id)

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    UPDATE tasks
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    values,
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def get_due_tasks(self, now: datetime) -> list[Task]:
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
                      AND next_run_at <= %s
                      AND status IN ('PENDING', 'COMPLETED', 'FAILED')
                    ORDER BY next_run_at ASC
                    LIMIT 100
                    """,
                    (now,),
                )
                rows = await cur.fetchall()

                return [Task(**row) for row in rows]

    async def mark_executed(
        self, task_id: UUID, executed_at: datetime, next_run: datetime | None
    ) -> Task | None:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE tasks
                    SET last_run_at = %s,
                        next_run_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, name, description, status, payload,
                              cron_expression, is_scheduled, next_run_at,
                              last_run_at, schedule_timezone, missed_run_policy,
                              created_at, updated_at
                    """,
                    (executed_at, next_run, task_id),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def get_task(self, task_id: UUID) -> Task | None:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, name, description, status, payload,
                           cron_expression, is_scheduled, next_run_at,
                           last_run_at, schedule_timezone, missed_run_policy,
                           created_at, updated_at
                    FROM tasks
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return Task(**row)

    async def list_scheduled_tasks(
        self,
        is_scheduled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                if is_scheduled is not None:
                    await cur.execute(
                        """
                        SELECT id, name, description, status, payload,
                               cron_expression, is_scheduled, next_run_at,
                               last_run_at, schedule_timezone, missed_run_policy,
                               created_at, updated_at
                        FROM tasks
                        WHERE is_scheduled = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (is_scheduled, limit, offset),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT id, name, description, status, payload,
                               cron_expression, is_scheduled, next_run_at,
                               last_run_at, schedule_timezone, missed_run_policy,
                               created_at, updated_at
                        FROM tasks
                        WHERE cron_expression IS NOT NULL
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
                rows = await cur.fetchall()

                return [Task(**row) for row in rows]
