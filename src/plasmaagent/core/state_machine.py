"""PostgreSQL Transactional State Machine (PTSM) implementation."""

from enum import Enum
from typing import Optional

import psycopg

from plasmaagent.core.exceptions import (
    InvalidStateTransitionError,
    TaskLockedError,
    TaskNotFoundError,
)


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Step status enum."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# Define valid state transitions
VALID_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {
        TaskStatus.PAUSED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.PENDING},  # Allow retry
    TaskStatus.COMPLETED: set(),  # Terminal state
    TaskStatus.CANCELLED: set(),  # Terminal state
}

VALID_STEP_TRANSITIONS: dict[StepStatus, set[StepStatus]] = {
    StepStatus.PENDING: {StepStatus.RUNNING, StepStatus.SKIPPED},
    StepStatus.RUNNING: {StepStatus.COMPLETED, StepStatus.FAILED},
    StepStatus.COMPLETED: set(),  # Terminal state
    StepStatus.FAILED: {StepStatus.PENDING},  # Allow retry
    StepStatus.SKIPPED: set(),  # Terminal state
}


async def transition_task_state(
    conn: psycopg.AsyncConnection,
    task_id: str,
    new_status: TaskStatus,
) -> bool:
    """Transition a task to a new state with atomic locking.

    Args:
        conn: Database connection
        task_id: Task UUID
        new_status: Target status

    Returns:
        bool: True if transition succeeded

    Raises:
        TaskNotFoundError: If task doesn't exist
        TaskLockedError: If task is locked by another process
        InvalidStateTransitionError: If transition is invalid
    """
    async with conn.cursor() as cur:
        # Lock the task row with FOR UPDATE SKIP LOCKED
        await cur.execute(
            """
            SELECT status FROM tasks
            WHERE id = %s
            FOR UPDATE SKIP LOCKED
            """,
            (task_id,),
        )
        result = await cur.fetchone()

        if result is None:
            # Check if task exists but is locked
            await cur.execute(
                "SELECT status FROM tasks WHERE id = %s",
                (task_id,),
            )
            if await cur.fetchone() is None:
                raise TaskNotFoundError(task_id)
            else:
                raise TaskLockedError(task_id)

        current_status = TaskStatus(result[0])

        # Validate transition
        if new_status not in VALID_TASK_TRANSITIONS.get(current_status, set()):
            raise InvalidStateTransitionError(
                current_status.value, new_status.value, task_id
            )

        # Perform transition
        await cur.execute(
            """
            UPDATE tasks
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_status.value, task_id),
        )

        return True


async def transition_step_state(
    conn: psycopg.AsyncConnection,
    step_id: str,
    new_status: StepStatus,
    output: Optional[str] = None,
) -> bool:
    """Transition a step to a new state.

    Args:
        conn: Database connection
        step_id: Step UUID
        new_status: Target status
        output: Optional output to store

    Returns:
        bool: True if transition succeeded

    Raises:
        TaskNotFoundError: If step doesn't exist
        InvalidStateTransitionError: If transition is invalid
    """
    async with conn.cursor() as cur:
        # Get current status
        await cur.execute(
            "SELECT status FROM task_steps WHERE id = %s FOR UPDATE",
            (step_id,),
        )
        result = await cur.fetchone()

        if result is None:
            raise TaskNotFoundError(step_id)

        current_status = StepStatus(result[0])

        # Validate transition
        if new_status not in VALID_STEP_TRANSITIONS.get(current_status, set()):
            raise InvalidStateTransitionError(
                current_status.value, new_status.value, step_id
            )

        # Build update query
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
            f"""
            UPDATE task_steps
            SET {', '.join(update_fields)}
            WHERE id = %s
            """,
            params,
        )

        return True


async def recover_crashed_tasks(conn: psycopg.AsyncConnection) -> int:
    """Recover tasks that were running when the system crashed.

    Marks RUNNING tasks as PAUSED so they can be manually resumed or retried.

    Args:
        conn: Database connection

    Returns:
        int: Number of tasks recovered
    """
    async with conn.cursor() as cur:
        # Find all RUNNING tasks
        await cur.execute(
            """
            SELECT id FROM tasks
            WHERE status = %s
            FOR UPDATE SKIP LOCKED
            """,
            (TaskStatus.RUNNING.value,),
        )
        running_tasks = await cur.fetchall()

        recovered_count = 0
        for task_row in running_tasks:
            task_id = task_row[0]

            # Mark as PAUSED
            await cur.execute(
                """
                UPDATE tasks
                SET status = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (TaskStatus.PAUSED.value, task_id),
            )

            # Mark any RUNNING steps as FAILED
            await cur.execute(
                """
                UPDATE task_steps
                SET status = %s, finished_at = NOW(),
                    output = COALESCE(output, '') || E'\n[CRASH RECOVERY] Task interrupted'
                WHERE task_id = %s AND status = %s
                """,
                (StepStatus.FAILED.value, task_id, StepStatus.RUNNING.value),
            )

            recovered_count += 1

        return recovered_count


def is_valid_task_transition(current: TaskStatus, target: TaskStatus) -> bool:
    """Check if a task state transition is valid.

    Args:
        current: Current status
        target: Target status

    Returns:
        bool: True if transition is valid
    """
    return target in VALID_TASK_TRANSITIONS.get(current, set())


def is_valid_step_transition(current: StepStatus, target: StepStatus) -> bool:
    """Check if a step state transition is valid.

    Args:
        current: Current status
        target: Target status

    Returns:
        bool: True if transition is valid
    """
    return target in VALID_STEP_TRANSITIONS.get(current, set())
