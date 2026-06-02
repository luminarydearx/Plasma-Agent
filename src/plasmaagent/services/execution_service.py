import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import psycopg

from plasmaagent.core.database import Database
from plasmaagent.core.state_machine import StepStatus, TaskStatus, transition_task_state
from plasmaagent.executor.result import ExecutionResult, OutputChunk, OutputSource
from plasmaagent.executor.shell import ShellExecutor
from plasmaagent.models.task import Task, TaskPayload


class ExecutionService:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def execute_task(
        self,
        task_id: UUID,
        on_step_start: Optional[Any] = None,
        on_step_output: Optional[Any] = None,
        on_step_complete: Optional[Any] = None,
    ) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.RUNNING)
            task = await self._load_task(conn, task_id)
            payload = self._extract_payload(task)

        if task.payload is None:
            raise ValueError(f"Task {task_id} has no payload")

        if not payload.commands:
            async with self._db.transaction() as conn:
                await transition_task_state(conn, str(task_id), TaskStatus.COMPLETED)
            return await self._reload_task(task_id)

        executor = ShellExecutor(
            timeout=payload.timeout,
            cwd=payload.cwd,
            env=payload.env if payload.env else None,
        )

        all_succeeded = True

        for step_order, command in enumerate(payload.commands, start=1):
            step_id = uuid4()

            async with self._db.transaction() as conn:
                await self._create_step(conn, task_id, step_id, step_order, command)
                await self._update_step_status(conn, step_id, StepStatus.RUNNING)
                await self._log_event(
                    conn,
                    task_id,
                    step_id,
                    "INFO",
                    f"Executing: {command}",
                )

            if on_step_start is not None:
                try:
                    await _maybe_await(on_step_start, step_order, command)
                except Exception:
                    pass

            async def _on_output(chunk: OutputChunk) -> None:
                level = "STDOUT" if chunk.source == OutputSource.STDOUT else "STDERR"
                lines = chunk.data.splitlines()
                
                async with self._db.transaction() as log_conn:
                    for line in lines:
                        await self._log_event(
                            log_conn, task_id, step_id, level, line
                        )
                
                if on_step_output is not None:
                    try:
                        await _maybe_await(on_step_output, step_order, chunk)
                    except Exception:
                        pass

            result = await executor.execute(command, str(task_id), on_output=_on_output)

            final_status = StepStatus.COMPLETED if result.succeeded else StepStatus.FAILED

            async with self._db.transaction() as conn:
                await self._finalize_step(conn, step_id, result, final_status)
                await self._log_event(
                    conn,
                    task_id,
                    step_id,
                    "INFO" if result.succeeded else "ERROR",
                    f"Step {step_order} finished: exit_code={result.exit_code}, "
                    f"duration={result.duration_ms}ms",
                )

            if on_step_complete is not None:
                try:
                    await _maybe_await(on_step_complete, step_order, result)
                except Exception:
                    pass

            if not result.succeeded:
                all_succeeded = False
                break

        async with self._db.transaction() as conn:
            final_task_status = (
                TaskStatus.COMPLETED if all_succeeded else TaskStatus.FAILED
            )
            await transition_task_state(conn, str(task_id), final_task_status)

        return await self._reload_task(task_id)

    async def _load_task(
        self,
        conn: psycopg.AsyncConnection,
        task_id: UUID,
    ) -> Task:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT id, name, description, status, payload, created_at, updated_at
                   FROM tasks WHERE id = %s""",
                (task_id,),
            )
            row = await cur.fetchone()
            if row is None:
                raise ValueError(f"Task not found: {task_id}")
            return Task(**row)

    async def _reload_task(self, task_id: UUID) -> Task:
        async with self._db.connection() as conn:
            return await self._load_task(conn, task_id)

    def _extract_payload(self, task: Task) -> TaskPayload:
        if task.payload is None:
            return TaskPayload(commands=[])
        return TaskPayload(**task.payload)

    async def _create_step(
        self,
        conn: psycopg.AsyncConnection,
        task_id: UUID,
        step_id: UUID,
        step_order: int,
        command: str,
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO task_steps (id, task_id, step_order, command, status)
                   VALUES (%s, %s, %s, %s, %s)""",
                (step_id, task_id, step_order, command, StepStatus.PENDING.value),
            )

    async def _update_step_status(
        self,
        conn: psycopg.AsyncConnection,
        step_id: UUID,
        status: StepStatus,
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE task_steps
                   SET status = %s, started_at = NOW()
                   WHERE id = %s""",
                (status.value, step_id),
            )

    async def _finalize_step(
        self,
        conn: psycopg.AsyncConnection,
        step_id: UUID,
        result: ExecutionResult,
        status: StepStatus,
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE task_steps
                   SET status = %s,
                       output = %s,
                       stderr = %s,
                       exit_code = %s,
                       duration_ms = %s,
                       finished_at = NOW()
                   WHERE id = %s""",
                (
                    status.value,
                    result.stdout or None,
                    result.stderr or None,
                    result.exit_code,
                    result.duration_ms,
                    step_id,
                ),
            )

    async def _log_event(
        self,
        conn: psycopg.AsyncConnection,
        task_id: UUID,
        step_id: UUID,
        level: str,
        message: str,
    ) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO execution_logs (task_id, step_id, log_level, message)
                   VALUES (%s, %s, %s, %s)""",
                (task_id, step_id, level, message),
            )


async def _maybe_await(func: Any, *args: Any) -> None:
    result = func(*args)
    if asyncio.iscoroutine(result):
        await result
