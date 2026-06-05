import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.database import Database
from plasmaagent.core.schema import Task, TaskStep, ExecutionLog
from plasmaagent.core.state_machine import StepStatus, TaskStatus, transition_task_state
from plasmaagent.executor.result import ExecutionResult, OutputChunk, OutputSource
from plasmaagent.executor.shell import ShellExecutor
from plasmaagent.models.task import TaskPayload


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
        async with self._db.transaction() as session:
            await transition_task_state(session, str(task_id), TaskStatus.RUNNING)
            task = await self._load_task(session, task_id)
            payload = self._extract_payload(task)

        if task.payload is None:
            raise ValueError(f"Task {task_id} has no payload")

        if not payload.commands:
            async with self._db.transaction() as session:
                await transition_task_state(session, str(task_id), TaskStatus.COMPLETED)
            return await self._reload_task(task_id)

        executor = ShellExecutor(
            timeout=payload.timeout,
            cwd=payload.cwd,
            env=payload.env if payload.env else None,
        )

        all_succeeded = True

        for step_order, command in enumerate(payload.commands, start=1):
            step_id = uuid4()

            async with self._db.transaction() as session:
                await self._create_step(session, task_id, step_id, step_order, command)
                await self._update_step_status(session, step_id, StepStatus.RUNNING)
                await self._log_event(
                    session,
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
                
                async with self._db.transaction() as log_session:
                    for line in lines:
                        await self._log_event(
                            log_session, task_id, step_id, level, line
                        )
                
                if on_step_output is not None:
                    try:
                        await _maybe_await(on_step_output, step_order, chunk)
                    except Exception:
                        pass

            result = await executor.execute(command, str(task_id), on_output=_on_output)

            final_status = StepStatus.COMPLETED if result.succeeded else StepStatus.FAILED

            async with self._db.transaction() as session:
                await self._finalize_step(session, step_id, result, final_status)
                await self._log_event(
                    session,
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

        async with self._db.transaction() as session:
            final_task_status = (
                TaskStatus.COMPLETED if all_succeeded else TaskStatus.FAILED
            )
            await transition_task_state(session, str(task_id), final_task_status)

        return await self._reload_task(task_id)

    async def _load_task(
        self,
        session: AsyncSession,
        task_id: UUID,
    ) -> Task:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task

    async def _reload_task(self, task_id: UUID) -> Task:
        async with self._db.session() as session:
            return await self._load_task(session, task_id)

    def _extract_payload(self, task: Task) -> TaskPayload:
        if task.payload is None:
            return TaskPayload(commands=[])
        return TaskPayload(**task.payload)

    async def _create_step(
        self,
        session: AsyncSession,
        task_id: UUID,
        step_id: UUID,
        step_order: int,
        command: str,
    ) -> None:
        step = TaskStep(
            id=step_id,
            task_id=task_id,
            step_order=step_order,
            command=command,
            status=StepStatus.PENDING.value,
        )
        session.add(step)
        await session.commit()

    async def _update_step_status(
        self,
        session: AsyncSession,
        step_id: UUID,
        status: StepStatus,
    ) -> None:
        stmt = select(TaskStep).where(TaskStep.id == step_id)
        result = await session.execute(stmt)
        step = result.scalar_one_or_none()
        
        if step:
            step.status = status.value
            step.started_at = datetime.now(timezone.utc)
            await session.commit()

    async def _finalize_step(
        self,
        session: AsyncSession,
        step_id: UUID,
        result: ExecutionResult,
        status: StepStatus,
    ) -> None:
        stmt = select(TaskStep).where(TaskStep.id == step_id)
        res = await session.execute(stmt)
        step = res.scalar_one_or_none()
        
        if step:
            step.status = status.value
            step.output = result.stdout or None
            step.stderr = result.stderr or None
            step.exit_code = result.exit_code
            step.duration_ms = result.duration_ms
            step.finished_at = datetime.now(timezone.utc)
            await session.commit()

    async def _log_event(
        self,
        session: AsyncSession,
        task_id: UUID,
        step_id: UUID,
        level: str,
        message: str,
    ) -> None:
        log = ExecutionLog(
            task_id=task_id,
            step_id=step_id,
            log_level=level,
            message=message,
        )
        session.add(log)
        await session.commit()


async def _maybe_await(func: Any, *args: Any) -> None:
    result = func(*args)
    if asyncio.iscoroutine(result):
        await result
