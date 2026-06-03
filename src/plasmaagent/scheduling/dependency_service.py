from uuid import UUID

from plasmaagent.core.database import Database
from plasmaagent.scheduling.dependencies import (
    DependencyType,
    TaskDependency,
    TaskDependencyCreate,
)
from plasmaagent.models.task import Task


class DependencyService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_dependency(self, data: TaskDependencyCreate) -> TaskDependency:
        if data.source_task_id == data.target_task_id:
            raise ValueError("Task cannot depend on itself")

        if await self._has_circular_dependency(
            data.source_task_id, data.target_task_id
        ):
            raise ValueError("Circular dependency detected")

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO task_dependencies (
                        source_task_id, target_task_id, dependency_type
                    ) VALUES (%s, %s, %s)
                    RETURNING id, source_task_id, target_task_id,
                              dependency_type, created_at
                    """,
                    (
                        data.source_task_id,
                        data.target_task_id,
                        data.dependency_type.value,
                    ),
                )
                row = await cur.fetchone()
                if not row:
                    raise RuntimeError("Failed to create dependency")

                return TaskDependency(**row)

    async def get_dependencies_for_task(
        self, task_id: UUID
    ) -> list[TaskDependency]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, source_task_id, target_task_id,
                           dependency_type, created_at
                    FROM task_dependencies
                    WHERE target_task_id = %s
                    ORDER BY created_at ASC
                    """,
                    (task_id,),
                )
                rows = await cur.fetchall()

                return [TaskDependency(**row) for row in rows]

    async def get_dependent_tasks(
        self, task_id: UUID
    ) -> list[TaskDependency]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, source_task_id, target_task_id,
                           dependency_type, created_at
                    FROM task_dependencies
                    WHERE source_task_id = %s
                    ORDER BY created_at ASC
                    """,
                    (task_id,),
                )
                rows = await cur.fetchall()

                return [TaskDependency(**row) for row in rows]

    async def delete_dependency(self, dependency_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM task_dependencies WHERE id = %s",
                    (dependency_id,),
                )
                return cur.rowcount > 0

    async def get_tasks_ready_to_run(self) -> list[UUID]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT DISTINCT td.target_task_id
                    FROM task_dependencies td
                    INNER JOIN tasks source ON td.source_task_id = source.id
                    WHERE (
                        (td.dependency_type = 'on_success' AND source.status = 'COMPLETED')
                        OR (td.dependency_type = 'on_failure' AND source.status = 'FAILED')
                        OR (td.dependency_type = 'on_complete' AND source.status IN ('COMPLETED', 'FAILED'))
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM task_dependencies td2
                        INNER JOIN tasks t2 ON td2.source_task_id = t2.id
                        WHERE td2.target_task_id = td.target_task_id
                        AND (
                            (td2.dependency_type = 'on_success' AND t2.status != 'COMPLETED')
                            OR (td2.dependency_type = 'on_failure' AND t2.status NOT IN ('FAILED', 'COMPLETED'))
                            OR (td2.dependency_type = 'on_complete' AND t2.status NOT IN ('COMPLETED', 'FAILED'))
                        )
                    )
                    """,
                )
                rows = await cur.fetchall()

                return [row["target_task_id"] for row in rows]

    async def _has_circular_dependency(
        self, source_id: UUID, target_id: UUID
    ) -> bool:
        visited = set()
        stack = [target_id]

        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                while stack:
                    current_id = stack.pop()

                    if current_id == source_id:
                        return True

                    if current_id in visited:
                        continue

                    visited.add(current_id)

                    await cur.execute(
                        """
                        SELECT target_task_id
                        FROM task_dependencies
                        WHERE source_task_id = %s
                        """,
                        (current_id,),
                    )
                    rows = await cur.fetchall()

                    for row in rows:
                        stack.append(row["target_task_id"])

        return False

    async def list_all_dependencies(
        self, limit: int = 100, offset: int = 0
    ) -> list[TaskDependency]:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, source_task_id, target_task_id,
                           dependency_type, created_at
                    FROM task_dependencies
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = await cur.fetchall()

                return [TaskDependency(**row) for row in rows]
