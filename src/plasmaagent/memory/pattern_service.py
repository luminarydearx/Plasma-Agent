import psycopg
from psycopg.types.json import Jsonb
from uuid import UUID, uuid4
from datetime import datetime, timezone
from plasmaagent.memory.models import TaskPattern


class PatternNotFoundError(Exception):
    def __init__(self, pattern_id: UUID):
        super().__init__(f"Task pattern {pattern_id} not found")
        self.pattern_id = pattern_id


class PatternService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn

    async def record_pattern(
        self,
        task_name: str,
        commands: list[str],
        user_id: UUID | None = None,
        duration_ms: float = 0.0,
        success: bool = True
    ) -> TaskPattern:
        pattern_id = uuid4()
        now = datetime.now(timezone.utc)
        confidence = 1.0 if success else 0.0
        success_count = 1 if success else 0

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO task_patterns
                (id, user_id, task_name, commands, success_count, avg_duration_ms, confidence, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (pattern_id, user_id, task_name, Jsonb(commands), success_count, duration_ms, confidence, now, now)
            )

        return TaskPattern(
            id=pattern_id,
            user_id=user_id,
            task_name=task_name,
            commands=commands,
            success_count=success_count,
            avg_duration_ms=duration_ms,
            confidence=confidence,
            created_at=now,
            updated_at=now
        )

    async def get_pattern(self, pattern_id: UUID) -> TaskPattern:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM task_patterns WHERE id = %s",
                (pattern_id,)
            )
            row = await cur.fetchone()

        if not row:
            raise PatternNotFoundError(pattern_id)

        return self._row_to_pattern(row)

    async def find_by_task_name(
        self,
        task_name: str,
        user_id: UUID | None = None,
        limit: int = 10
    ) -> list[TaskPattern]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not task_name or len(task_name) > 200:
            raise ValueError("task_name must be 1-200 characters")

        if user_id:
            async with self._conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM task_patterns
                    WHERE task_name ILIKE %s AND user_id = %s
                    ORDER BY confidence DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (f"%{task_name}%", user_id, limit)
                )
                rows = await cur.fetchall()
        else:
            async with self._conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM task_patterns
                    WHERE task_name ILIKE %s
                    ORDER BY confidence DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (f"%{task_name}%", limit)
                )
                rows = await cur.fetchall()

        return [self._row_to_pattern(row) for row in rows]

    async def update_success(
        self,
        pattern_id: UUID,
        duration_ms: float,
        success: bool = True
    ) -> TaskPattern:
        now = datetime.now(timezone.utc)

        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT success_count, avg_duration_ms FROM task_patterns WHERE id = %s",
                (pattern_id,)
            )
            row = await cur.fetchone()

            if not row:
                raise PatternNotFoundError(pattern_id)

            old_count = row["success_count"]
            old_avg = row["avg_duration_ms"]
            new_count = old_count + (1 if success else 0)
            total_runs = old_count + 1
            new_avg = ((old_avg * old_count) + duration_ms) / total_runs if total_runs > 0 else duration_ms
            new_confidence = new_count / total_runs if total_runs > 0 else 0.0

            await cur.execute(
                """
                UPDATE task_patterns
                SET success_count = %s, avg_duration_ms = %s, confidence = %s, updated_at = %s
                WHERE id = %s
                """,
                (new_count, new_avg, new_confidence, now, pattern_id)
            )

            await cur.execute(
                "SELECT * FROM task_patterns WHERE id = %s",
                (pattern_id,)
            )
            updated_row = await cur.fetchone()

        return self._row_to_pattern(updated_row)

    async def delete_pattern(self, pattern_id: UUID) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM task_patterns WHERE id = %s",
                (pattern_id,)
            )
            if cur.rowcount == 0:
                raise PatternNotFoundError(pattern_id)

    async def get_top_patterns(
        self,
        user_id: UUID | None = None,
        limit: int = 20
    ) -> list[TaskPattern]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if user_id:
            async with self._conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM task_patterns
                    WHERE user_id = %s
                    ORDER BY confidence DESC, success_count DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                rows = await cur.fetchall()
        else:
            async with self._conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM task_patterns
                    ORDER BY confidence DESC, success_count DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = await cur.fetchall()

        return [self._row_to_pattern(row) for row in rows]

    def _row_to_pattern(self, row: dict) -> TaskPattern:
        commands = row["commands"]
        if isinstance(commands, str):
            import json
            commands = json.loads(commands)

        return TaskPattern(
            id=row["id"],
            user_id=row.get("user_id"),
            task_name=row["task_name"],
            commands=commands,
            success_count=row["success_count"],
            avg_duration_ms=row["avg_duration_ms"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
