from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from plasmaagent.core.database import Database
from plasmaagent.scheduling.state import SchedulerState


class SchedulerPersistence:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def save_state(
        self,
        is_running: bool,
        last_check_at: datetime | None = None,
        active_task_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> SchedulerState:
        state_id = uuid4()
        now = datetime.now()

        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO scheduler_state (
                        id, is_running, last_check_at, active_task_count,
                        metadata, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        is_running = EXCLUDED.is_running,
                        last_check_at = EXCLUDED.last_check_at,
                        active_task_count = EXCLUDED.active_task_count,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id, is_running, last_check_at, active_task_count,
                              metadata, updated_at
                    """,
                    (
                        state_id,
                        is_running,
                        last_check_at,
                        active_task_count,
                        metadata or {},
                        now,
                    ),
                )
                row = await cur.fetchone()
                if not row:
                    raise RuntimeError("Failed to save scheduler state")

                return SchedulerState(**row)

    async def load_state(self) -> SchedulerState | None:
        async with self._db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, is_running, last_check_at, active_task_count,
                           metadata, updated_at
                    FROM scheduler_state
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                )
                row = await cur.fetchone()
                if not row:
                    return None

                return SchedulerState(**row)

    async def clear_state(self) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM scheduler_state")
                return True

    async def update_last_check(self, check_at: datetime) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE scheduler_state
                    SET last_check_at = %s, updated_at = NOW()
                    WHERE id IN (
                        SELECT id FROM scheduler_state
                        ORDER BY updated_at DESC
                        LIMIT 1
                    )
                    """,
                    (check_at,),
                )
                return cur.rowcount > 0

    async def update_active_tasks(self, count: int) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE scheduler_state
                    SET active_task_count = %s, updated_at = NOW()
                    WHERE id IN (
                        SELECT id FROM scheduler_state
                        ORDER BY updated_at DESC
                        LIMIT 1
                    )
                    """,
                    (count,),
                )
                return cur.rowcount > 0

    async def get_recovery_info(self) -> dict[str, Any]:
        state = await self.load_state()
        if not state:
            return {
                "needs_recovery": False,
                "was_running": False,
                "last_check": None,
                "active_tasks": 0,
            }

        return {
            "needs_recovery": state.is_running,
            "was_running": state.is_running,
            "last_check": state.last_check_at,
            "active_tasks": state.active_task_count,
            "metadata": state.metadata,
        }
