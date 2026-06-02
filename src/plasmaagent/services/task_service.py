import json
from typing import Any, Optional
from uuid import UUID

from plasmaagent.core.database import Database, get_database
from plasmaagent.core.exceptions import TaskNotFoundError
from plasmaagent.core.state_machine import TaskStatus, transition_task_state
from plasmaagent.models.task import Task, TaskCreate, TaskPayload


class TaskService:
    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or get_database()

    async def create_task(self, task_data: TaskCreate) -> Task:
        payload_json: Optional[str] = None
        if task_data.payload is not None:
            payload_json = json.dumps(task_data.payload.model_dump())

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO tasks (name, description, status, payload)
                       VALUES (%s, %s, %s, %s::jsonb)
                       RETURNING id, name, description, status, payload,
                                 created_at, updated_at""",
                    (
                        task_data.name,
                        task_data.description,
                        TaskStatus.PENDING.value,
                        payload_json,
                    ),
                )
                result = await cur.fetchone()
                return Task(**result)

    async def get_task(self, task_id: UUID) -> Task:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, name, description, status, payload,
                              created_at, updated_at
                       FROM tasks WHERE id = %s""",
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
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                if status:
                    await cur.execute(
                        """SELECT id, name, description, status, payload,
                                  created_at, updated_at
                           FROM tasks WHERE status = %s
                           ORDER BY created_at DESC
                           LIMIT %s OFFSET %s""",
                        (status.value, limit, offset),
                    )
                else:
                    await cur.execute(
                        """SELECT id, name, description, status, payload,
                                  created_at, updated_at
                           FROM tasks
                           ORDER BY created_at DESC
                           LIMIT %s OFFSET %s""",
                        (limit, offset),
                    )
                results = await cur.fetchall()
                return [Task(**row) for row in results]

    async def run_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.RUNNING)
        return await self.get_task(task_id)

    async def pause_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.PAUSED)
        return await self.get_task(task_id)

    async def complete_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.COMPLETED)
        return await self.get_task(task_id)

    async def fail_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.FAILED)
        return await self.get_task(task_id)

    async def cancel_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.CANCELLED)
        return await self.get_task(task_id)

    async def retry_task(self, task_id: UUID) -> Task:
        async with self._db.transaction() as conn:
            await transition_task_state(conn, str(task_id), TaskStatus.PENDING)
        return await self.get_task(task_id)

    async def delete_task(self, task_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                return cur.rowcount > 0

    async def get_task_steps(self, task_id: UUID) -> list[dict[str, Any]]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, step_order, command, status, output, stderr,
                              exit_code, duration_ms, started_at, finished_at
                       FROM task_steps
                       WHERE task_id = %s
                       ORDER BY step_order ASC""",
                    (task_id,),
                )
                return await cur.fetchall()

    async def get_execution_logs(
        self,
        task_id: UUID,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT id, step_id, log_level, message, timestamp
                       FROM execution_logs
                       WHERE task_id = %s
                       ORDER BY timestamp ASC
                       LIMIT %s""",
                    (task_id, limit),
                )
                return await cur.fetchall()
