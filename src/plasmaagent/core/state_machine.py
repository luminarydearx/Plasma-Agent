from enum import Enum
from typing import Optional

import psycopg

from plasmaagent.core.exceptions import (
    InvalidStateTransitionError,
    TaskLockedError,
    TaskNotFoundError,
)


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
    conn: psycopg.AsyncConnection,
    task_id: str,
    new_status: TaskStatus,
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM tasks WHERE id = %s FOR UPDATE SKIP LOCKED",
            (task_id,),
        )
        result = await cur.fetchone()

        if result is None:
            await cur.execute(
                "SELECT status FROM tasks WHERE id = %s",
                (task_id,),
            )
            locked_result = await cur.fetchone()
            if locked_result is None:
                raise TaskNotFoundError(task_id)
            else:
                raise TaskLockedError(task_id)

        current_status = TaskStatus(result["status"])

        if new_status not in VALID_TASK_TRANSITIONS.get(current_status, set()):
            raise InvalidStateTransitionError(
                current_status.value, new_status.value, task_id
            )

        await cur.execute(
            "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status.value, task_id),
        )
        return True


async def transition_step_state(
    conn: psycopg.AsyncConnection,
    step_id: str,
    new_status: StepStatus,
    output: Optional[str] = None,
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM task_steps WHERE id = %s FOR UPDATE",
            (step_id,),
        )
        result = await cur.fetchone()
        if result is None:
            raise TaskNotFoundError(step_id)

        current_status = StepStatus(result["status"])

        if new_status not in VALID_STEP_TRANSITIONS.get(current_status, set()):
            raise InvalidStateTransitionError(
                current_status.value, new_status.value, step_id
            )

        update_fields = ["status = %s"]
        params: list = [new_status.value]

        if new_status == StepStatus.RUNNING:
            update_fields.append("started_at = NOW()")
        elif new_status in {StepStatus.COMPLETED, StepStatus.FAILED}:
            update_fields.append("finished_at = NOW()")

        if output is not None:
            update_fields.append("output = %s")
            params.append(output)

        params.append(step_id)

        await cur.execute(
            f"UPDATE task_steps SET {', '.join(update_fields)} WHERE id = %s",
            params,
        )
        return True


async def recover_crashed_tasks(conn: psycopg.AsyncConnection) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM tasks WHERE status = %s FOR UPDATE SKIP LOCKED",
            (TaskStatus.RUNNING.value,),
        )
        running_tasks = await cur.fetchall()
        recovered_count = 0

        for task_row in running_tasks:
            task_id = task_row["id"]
            await cur.execute(
                "UPDATE tasks SET status = %s, updated_at = NOW() WHERE id = %s",
                (TaskStatus.PAUSED.value, task_id),
            )
            await cur.execute(
                """UPDATE task_steps
                   SET status = %s, finished_at = NOW(),
                       output = COALESCE(output, '') || E'\n[CRASH RECOVERY] Task interrupted'
                   WHERE task_id = %s AND status = %s""",
                (StepStatus.FAILED.value, task_id, StepStatus.RUNNING.value),
            )
            recovered_count += 1

        return recovered_count


def is_valid_task_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in VALID_TASK_TRANSITIONS.get(current, set())


def is_valid_step_transition(current: StepStatus, target: StepStatus) -> bool:
    return target in VALID_STEP_TRANSITIONS.get(current, set())
