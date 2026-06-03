from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID

from plasmaagent.core.database import Database
from plasmaagent.models.task import MissedRunPolicy
from plasmaagent.scheduling.cron_parser import CronParser


logger = logging.getLogger(__name__)


ExecutionCallback = Callable[[UUID], Coroutine[Any, Any, bool]]


class SchedulerService:
    def __init__(
        self,
        db: Database,
        execution_callback: Optional[ExecutionCallback] = None,
        check_interval_seconds: int = 60,
        catch_up_on_miss: bool = True,
    ) -> None:
        self._db = db
        self._execution_callback = execution_callback
        self._check_interval = max(1, check_interval_seconds)
        self._catch_up_on_miss = catch_up_on_miss
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("SchedulerService started (interval=%ds)", self._check_interval)

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return
            self._running = False
            if self._task is not None:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
            logger.info("SchedulerService stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Scheduler tick failed: %s", exc)
            
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                raise

    async def _tick(self) -> int:
        now = datetime.now(timezone.utc)
        due_tasks = await self._get_due_tasks(now)
        executed = 0
        
        for task_data in due_tasks:
            task_id: UUID = task_data["id"]
            try:
                async with self._db.transaction() as conn:
                    locked = await self._lock_task(conn, task_id, now)
                    if not locked:
                        continue
                
                success = await self._execute_task(task_id)
                
                async with self._db.transaction() as conn:
                    await self._update_after_execution(
                        conn,
                        task_id,
                        task_data["cron_expression"],
                        now,
                        success,
                    )
                
                executed += 1
            except Exception as exc:
                logger.exception("Failed to execute scheduled task %s: %s", task_id, exc)
        
        return executed

    async def _get_due_tasks(self, now: datetime) -> list[dict[str, Any]]:
        query = """
            SELECT id, cron_expression, missed_run_policy, last_run_at
            FROM tasks
            WHERE is_scheduled = true
              AND status != 'DELETED'
              AND cron_expression IS NOT NULL
              AND next_run_at <= %s
            ORDER BY next_run_at ASC
            LIMIT 100
        """
        
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (now,))
                rows = await cur.fetchall()
        
        return [
            {
                "id": row["id"],
                "cron_expression": row["cron_expression"],
                "missed_run_policy": row["missed_run_policy"],
                "last_run_at": row["last_run_at"],
            }
            for row in rows
        ]

    async def _lock_task(self, conn: Any, task_id: UUID, now: datetime) -> bool:
        query = """
            UPDATE tasks
            SET status = 'RUNNING', updated_at = %s
            WHERE id = %s
              AND status NOT IN ('RUNNING', 'DELETED')
            RETURNING id
        """
        async with conn.cursor() as cur:
            await cur.execute(query, (now, task_id))
            row = await cur.fetchone()
        return row is not None

    async def _execute_task(self, task_id: UUID) -> bool:
        if self._execution_callback is None:
            logger.warning("No execution callback configured for task %s", task_id)
            return False
        
        try:
            return await self._execution_callback(task_id)
        except Exception as exc:
            logger.exception("Execution callback failed for %s: %s", task_id, exc)
            return False

    async def _update_after_execution(
        self,
        conn: Any,
        task_id: UUID,
        cron_expression: str,
        executed_at: datetime,
        success: bool,
    ) -> None:
        try:
            cron = CronParser.parse(cron_expression)
            next_run = cron.next_run(after=executed_at)
        except Exception as exc:
            logger.warning("Invalid cron expression for task %s: %s", task_id, exc)
            next_run = None
        
        new_status = "COMPLETED" if success else "FAILED"
        
        query = """
            UPDATE tasks
            SET status = %s,
                last_run_at = %s,
                next_run_at = %s,
                updated_at = %s
            WHERE id = %s
        """
        async with conn.cursor() as cur:
            await cur.execute(query, (new_status, executed_at, next_run, executed_at, task_id))

    async def schedule_task(
        self,
        task_id: UUID,
        cron_expression: str,
        timezone_name: Optional[str] = None,
        missed_run_policy: MissedRunPolicy = "skip",
    ) -> datetime:
        cron = CronParser.parse(cron_expression)
        now = datetime.now(timezone.utc)
        next_run = cron.next_run(after=now)
        
        query = """
            UPDATE tasks
            SET cron_expression = %s,
                schedule_timezone = %s,
                missed_run_policy = %s,
                next_run_at = %s,
                is_scheduled = true,
                updated_at = %s
            WHERE id = %s AND status != 'DELETED'
            RETURNING id
        """
        
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (cron_expression, timezone_name, missed_run_policy, next_run, now, task_id),
                )
                row = await cur.fetchone()
        
        if row is None:
            raise ValueError(f"Task {task_id} not found or deleted")
        
        return next_run

    async def unschedule_task(self, task_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        query = """
            UPDATE tasks
            SET is_scheduled = false,
                next_run_at = NULL,
                updated_at = %s
            WHERE id = %s
        """
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (now, task_id))

    async def get_scheduled_tasks(self) -> list[dict[str, Any]]:
        query = """
            SELECT id, name, cron_expression, next_run_at, last_run_at,
                   status, missed_run_policy
            FROM tasks
            WHERE is_scheduled = true
              AND status != 'DELETED'
            ORDER BY next_run_at ASC
        """
        
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
        
        return [dict(row) for row in rows]

    async def handle_missed_executions(self, task_id: UUID) -> int:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT cron_expression, missed_run_policy, last_run_at, next_run_at FROM tasks WHERE id = %s",
                    (task_id,),
                )
                row = await cur.fetchone()
        
        if row is None or row["cron_expression"] is None:
            return 0
        
        policy: MissedRunPolicy = row["missed_run_policy"]
        cron_expr: str = row["cron_expression"]
        next_run: Optional[datetime] = row["next_run_at"]
        now = datetime.now(timezone.utc)
        
        if next_run is None or next_run >= now:
            return 0
        
        if policy == "skip":
            cron = CronParser.parse(cron_expr)
            new_next_run = cron.next_run(after=now)
            
            async with self._db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE tasks SET next_run_at = %s, updated_at = %s WHERE id = %s",
                        (new_next_run, now, task_id),
                    )
            return 0
        
        missed_count = 0
        cron = CronParser.parse(cron_expr)
        current = next_run
        
        if policy == "run_once":
            missed_count = 1
        elif policy == "run_all":
            while current <= now:
                missed_count += 1
                current = cron.next_run(after=current)
                if missed_count > 100:
                    break
        
        new_next_run = cron.next_run(after=now)
        
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE tasks SET next_run_at = %s, updated_at = %s WHERE id = %s",
                    (new_next_run, now, task_id),
                )
        
        for _ in range(missed_count):
            try:
                await self._execute_task(task_id)
            except Exception as exc:
                logger.exception("Missed execution failed for %s: %s", task_id, exc)
        
        return missed_count
