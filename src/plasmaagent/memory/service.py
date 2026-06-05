from uuid import UUID, uuid4
from datetime import datetime
import psycopg
from plasmaagent.memory.models import Memory, MemoryType, MemoryStats


class MemoryNotFoundError(Exception):
    def __init__(self, memory_id: UUID):
        self.memory_id = memory_id
        super().__init__(f"Memory {memory_id} not found")


class MemoryService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn

    async def store_memory(
        self,
        content: str,
        memory_type: MemoryType,
        user_id: UUID | None = None,
        metadata: dict | None = None,
        embedding: list[float] | None = None
    ) -> Memory:
        memory_id = uuid4()
        now = datetime.now()
        metadata = metadata or {}
        embedding_str = str(embedding) if embedding else None

        await self._conn.execute(
            """
            INSERT INTO memories (id, user_id, content, embedding, metadata, memory_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (memory_id, user_id, content, embedding_str, metadata, memory_type.value, now, now)
        )

        return Memory(
            id=memory_id,
            user_id=user_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
            memory_type=memory_type,
            created_at=now,
            updated_at=now
        )

    async def get_memory(self, memory_id: UUID) -> Memory:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM memories WHERE id = %s",
                (memory_id,)
            )
            row = await cur.fetchone()

        if not row:
            raise MemoryNotFoundError(memory_id)

        return self._row_to_memory(row)

    async def delete_memory(self, memory_id: UUID) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM memories WHERE id = %s",
                (memory_id,)
            )

            if cur.rowcount == 0:
                raise MemoryNotFoundError(memory_id)

    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        memory_type: MemoryType | None = None,
        user_id: UUID | None = None
    ) -> list[Memory]:
        conditions = ["content ILIKE %s"]
        params = [f"%{query}%"]

        if memory_type:
            conditions.append("memory_type = %s")
            params.append(memory_type.value)

        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        async with self._conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT * FROM memories
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params
            )
            rows = await cur.fetchall()

        return [self._row_to_memory(row) for row in rows]

    async def get_memories_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
        user_id: UUID | None = None
    ) -> list[Memory]:
        async with self._conn.cursor() as cur:
            if user_id:
                await cur.execute(
                    """
                    SELECT * FROM memories
                    WHERE memory_type = %s AND user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (memory_type.value, user_id, limit)
                )
            else:
                await cur.execute(
                    """
                    SELECT * FROM memories
                    WHERE memory_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (memory_type.value, limit)
                )
            rows = await cur.fetchall()

        return [self._row_to_memory(row) for row in rows]

    async def get_stats(self) -> MemoryStats:
        async with self._conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM memories")
            total = (await cur.fetchone())[0]

            await cur.execute(
                "SELECT memory_type, COUNT(*) as count FROM memories GROUP BY memory_type"
            )
            type_counts = await cur.fetchall()
            memories_by_type = {row[0]: row[1] for row in type_counts}

            await cur.execute("SELECT COUNT(*) FROM conversation_sessions")
            total_conversations = (await cur.fetchone())[0]

            await cur.execute("SELECT COUNT(*) FROM task_patterns")
            total_patterns = (await cur.fetchone())[0]

        return MemoryStats(
            total_memories=total or 0,
            memories_by_type=memories_by_type,
            total_conversations=total_conversations or 0,
            total_patterns=total_patterns or 0,
            avg_embedding_dimensions=384
        )

    def _row_to_memory(self, row) -> Memory:
        embedding = None
        if row[3]:
            try:
                embedding = eval(row[3])
            except:
                embedding = None

        return Memory(
            id=row[0],
            user_id=row[1],
            content=row[2],
            embedding=embedding,
            metadata=row[4],
            memory_type=MemoryType(row[5]),
            created_at=row[6],
            updated_at=row[7]
        )
