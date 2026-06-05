import json
from typing import Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import text

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

        new_id = str(uuid4())
        now = datetime.now(timezone.utc)

        await self._db.execute(
            """INSERT INTO tasks (id, name, description, status, payload, created_at, updated_at)
               VALUES (:id, :name, :desc, :status, :payload, :created, :updated)""",
            {
                "id": new_id,
                "name": task_data.name,
                "desc": task_data.description or "",
                "status": TaskStatus.PENDING.value,
                "payload": payload_json,
                "created": now,
                "updated": now,
            },
        )

        return Task(
            id=new_id,
            name=task_data.name,
            description=task_data.description or "",
            status=TaskStatus.PENDING.value,
            payload=payload_json,
            created_at=now,
            updated_at=now,
        )

    async def get_task(self, task_id: UUID) -> Task:
        row = await self._db.fetch_one(
            """SELECT id, name, description, status, payload,
                      created_at, updated_at
               FROM tasks WHERE id = :id""",
            {"id": str(task_id)},
        )
        if row is None:
            raise TaskNotFoundError(str(task_id))
        return Task(**row)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        if status:
            rows = await self._db.fetch_all(
                """SELECT id, name, description, status, payload,
                          created_at, updated_at
                   FROM tasks WHERE status = :status
                   ORDER BY created_at DESC
                   LIMIT :limit OFFSET :offset""",
                {"status": status.value, "limit": limit, "offset": offset},
            )
        else:
            rows = await self._db.fetch_all(
                """SELECT id, name, description, status, payload,
                          created_at, updated_at
                   FROM tasks
                   ORDER BY created_at DESC
                   LIMIT :limit OFFSET :offset""",
                {"limit": limit, "offset": offset},
            )
        return [Task(**row) for row in rows]

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
            result = await conn.execute(
                text("DELETE FROM tasks WHERE id = :id"),
                {"id": str(task_id)},
            )
            return result.rowcount > 0

    async def get_task_steps(self, task_id: UUID) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """SELECT id, step_order, command, status, output, stderr,
                      exit_code, duration_ms, started_at, finished_at
               FROM task_steps
               WHERE task_id = :task_id
               ORDER BY step_order ASC""",
            {"task_id": str(task_id)},
        )

    async def get_execution_logs(
        self,
        task_id: UUID,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """SELECT id, step_id, log_level, message, timestamp
               FROM execution_logs
               WHERE task_id = :task_id
               ORDER BY timestamp ASC
               LIMIT :limit""",
            {"task_id": str(task_id), "limit": limit},
        )
