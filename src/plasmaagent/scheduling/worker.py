import asyncio
from datetime import datetime
from typing import Any, Callable, Coroutine

import structlog

from plasmaagent.core.database import Database
from plasmaagent.scheduling.service import SchedulingService
from plasmaagent.scheduling.cron_parser import CronParser
from plasmaagent.models.task import Task

logger = structlog.get_logger()


class SchedulerWorker:
    def __init__(
        self,
        db: Database,
        task_executor: Callable[[Task], Coroutine[Any, Any, None]],
        check_interval: int = 60,
        max_concurrent: int = 10,
    ) -> None:
        self._db = db
        self._service = SchedulingService(db)
        self._task_executor = task_executor
        self._check_interval = check_interval
        self._max_concurrent = max_concurrent
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info(
            "Scheduler started",
            check_interval=self._check_interval,
            max_concurrent=self._max_concurrent,
        )

        try:
            while self._running:
                try:
                    await self._check_and_execute()
                except Exception as e:
                    logger.error("Scheduler check failed", error=str(e))

                await asyncio.sleep(self._check_interval)
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        finally:
            self._running = False
            await self._cleanup()

    async def stop(self) -> None:
        if not self._running:
            return

        logger.info("Stopping scheduler")
        self._running = False

        for task_id, task in self._active_tasks.items():
            task.cancel()
            logger.info("Cancelled task", task_id=task_id)

        await self._cleanup()
        logger.info("Scheduler stopped")

    async def _check_and_execute(self) -> None:
        now = datetime.now()
        due_tasks = await self._service.get_due_tasks(now)

        if not due_tasks:
            return

        logger.info("Found due tasks", count=len(due_tasks))

        for task in due_tasks:
            if str(task.id) in self._active_tasks:
                logger.debug("Task already running", task_id=str(task.id))
                continue

            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: Task) -> None:
        task_id_str = str(task.id)

        async with self._semaphore:
            self._active_tasks[task_id_str] = asyncio.current_task()  # type: ignore

            try:
                logger.info(
                    "Executing scheduled task",
                    task_id=task_id_str,
                    task_name=task.name,
                    cron=task.cron_expression,
                )

                executed_at = datetime.now()

                await self._task_executor(task)

                if task.cron_expression:
                    cron_expr = CronParser.parse(task.cron_expression)
                    next_run = cron_expr.next_run(executed_at)
                else:
                    next_run = None

                await self._service.mark_executed(task.id, executed_at, next_run)

                logger.info(
                    "Scheduled task completed",
                    task_id=task_id_str,
                    next_run=next_run,
                )

            except Exception as e:
                logger.error(
                    "Scheduled task failed",
                    task_id=task_id_str,
                    error=str(e),
                )

                if task.missed_run_policy == "catch_up" and task.cron_expression:
                    cron_expr = CronParser.parse(task.cron_expression)
                    next_run = cron_expr.next_run(datetime.now())
                    await self._service.mark_executed(task.id, datetime.now(), next_run)

            finally:
                self._active_tasks.pop(task_id_str, None)

    async def _cleanup(self) -> None:
        if self._active_tasks:
            logger.info(
                "Waiting for active tasks to complete",
                count=len(self._active_tasks),
            )

            tasks = list(self._active_tasks.values())
            await asyncio.gather(*tasks, return_exceptions=True)

            self._active_tasks.clear()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_task_count(self) -> int:
        return len(self._active_tasks)
