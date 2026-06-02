"""Task service for CRUD and lifecycle operations."""

from typing import Optional
from uuid import UUID

import psycopg

from plasmaagent.core.database import Database, get_database
from plasmaagent.core.exceptions import TaskNotFoundError
from plasmaagent.core.state_machine import TaskStatus, transition_task_state
from plasmaagent.models.task import Task, TaskCreate


class TaskService:
    """Service for task operations."""

    def __init__(self, database: Optional[Database] = None):
        """Initialize task service.

        Args:
            database: Optional database instance
        """
        self._db = database or get_database()

    async def create_task(self, task_data: TaskCreate) -> Task:
        """Create a new task.

        Args:
            task_data: Task creation data

        Returns:
            Task: Created task
        """
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO tasks (name, description, status)
                    VALUES (%s, %s, %s)
                    RETURNING id, name, description, status, created_at, updated_at
                    """,
                    (task_data.name, task_data.description, TaskStatus.PENDING.value),
                )
                result = await cur.fetchone()
                return Task(**result)

    async def get_task(self, task_id: UUID) -> Task:
        """Get a task by ID.

        Args:
            task_id: Task UUID

        Returns:
            Task: Retrieved task

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, name, description, status, created_at, updated_at
                    FROM tasks
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                result = await cur.fetchone()
                if result is None:
                    raise TaskNotFoundError(str(task_id))
                return Task(**result)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            list[Task]: List of tasks
        """
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                if status:
                    await cur.execute(
                        """
                        SELECT id, name, description, status, created_at, updated_at
                        FROM tasks
                        WHERE status = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (status.value, limit, offset),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT id, name, description, status, created_at, updated_at
                        FROM tasks
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
                results = await cur.fetchall()
                return [Task(**row) for row in results]

    async def run_task(self, task_id: UUID) -> Task:
        """Transition a task to RUNNING state.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.RUNNING)
        return await self.get_task(task_id)

    async def pause_task(self, task_id: UUID) -> Task:
        """Transition a task to PAUSED state.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.PAUSED)
        return await self.get_task(task_id)

    async def complete_task(self, task_id: UUID) -> Task:
        """Transition a task to COMPLETED state.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.COMPLETED)
        return await self.get_task(task_id)

    async def fail_task(self, task_id: UUID) -> Task:
        """Transition a task to FAILED state.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.FAILED)
        return await self.get_task(task_id)

    async def cancel_task(self, task_id: UUID) -> Task:
        """Transition a task to CANCELLED state.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.CANCELLED)
        return await self.get_task(task_id)

    async def retry_task(self, task_id: UUID) -> Task:
        """Retry a failed task by resetting to PENDING.

        Args:
            task_id: Task UUID

        Returns:
            Task: Updated task
        """
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.PENDING)
        return await self.get_task(task_id)

    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task.

        Args:
            task_id: Task UUID

        Returns:
            bool: True if deleted
        """
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                return cur.rowcount > 0
