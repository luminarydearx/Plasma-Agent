from enum import Enum
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.exceptions import (
    InvalidStateTransitionError,
    TaskLockedError,
    TaskNotFoundError,
)
from plasmaagent.core.schema import Task, TaskStep


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


VALID_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.PAUSED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.PENDING},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}

VALID_STEP_TRANSITIONS: dict[StepStatus, set[StepStatus]] = {
    StepStatus.PENDING: {StepStatus.RUNNING, StepStatus.SKIPPED},
    StepStatus.RUNNING: {StepStatus.COMPLETED, StepStatus.FAILED},
    StepStatus.COMPLETED: set(),
    StepStatus.FAILED: {StepStatus.PENDING},
    StepStatus.SKIPPED: set(),
}


async def transition_task_state(
    session: AsyncSession,
    task_id: str,
    new_status: TaskStatus,
) -> bool:
    from uuid import UUID
    task_uuid = UUID(task_id) if isinstance(task_id, str) else task_id
    
    stmt = select(Task).where(Task.id == task_uuid).with_for_update()
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        check_stmt = select(Task).where(Task.id == task_uuid)
        check_result = await session.execute(check_stmt)
        if check_result.scalar_one_or_none() is None:
            raise TaskNotFoundError(task_id)
        else:
            raise TaskLockedError(task_id)

    current_status = TaskStatus(task.status)

    if new_status not in VALID_TASK_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(
            current_status.value, new_status.value, task_id
        )

    from datetime import datetime, timezone
    task.status = new_status.value
    task.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def transition_step_state(
    session: AsyncSession,
    step_id: str,
    new_status: StepStatus,
    output: Optional[str] = None,
) -> bool:
    from uuid import UUID
    from datetime import datetime, timezone
    
    step_uuid = UUID(step_id) if isinstance(step_id, str) else step_id
    
    stmt = select(TaskStep).where(TaskStep.id == step_uuid).with_for_update()
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    
    if step is None:
        raise TaskNotFoundError(step_id)

    current_status = StepStatus(step.status)

    if new_status not in VALID_STEP_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(
            current_status.value, new_status.value, step_id
        )

    step.status = new_status.value
    
    now = datetime.now(timezone.utc)
    if new_status == StepStatus.RUNNING:
        step.started_at = now
    elif new_status in {StepStatus.COMPLETED, StepStatus.FAILED}:
        step.finished_at = now

    if output is not None:
        step.output = output

    await session.commit()
    return True


async def recover_crashed_tasks(session: AsyncSession) -> int:
    from uuid import UUID
    from datetime import datetime, timezone
    
    stmt = select(Task).where(Task.status == TaskStatus.RUNNING.value).with_for_update()
    result = await session.execute(stmt)
    running_tasks = result.scalars().all()
    
    recovered_count = 0
    now = datetime.now(timezone.utc)

    for task in running_tasks:
        task.status = TaskStatus.PAUSED.value
        task.updated_at = now
        
        step_stmt = select(TaskStep).where(
            TaskStep.task_id == task.id,
            TaskStep.status == StepStatus.RUNNING.value
        )
        step_result = await session.execute(step_stmt)
        running_steps = step_result.scalars().all()
        
        for step in running_steps:
            step.status = StepStatus.FAILED.value
            step.finished_at = now
            step.output = (step.output or "") + "\n[CRASH RECOVERY] Task interrupted"
        
        recovered_count += 1

    await session.commit()
    return recovered_count


def is_valid_task_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in VALID_TASK_TRANSITIONS.get(current, set())


def is_valid_step_transition(current: StepStatus, target: StepStatus) -> bool:
    return target in VALID_STEP_TRANSITIONS.get(current, set())
