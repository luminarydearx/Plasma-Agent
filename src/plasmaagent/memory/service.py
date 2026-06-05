from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from plasmaagent.memory.models import Memory, MemoryStats, MemoryType


class MemoryNotFoundError(Exception):
    def __init__(self, memory_id: UUID):
        self.memory_id = memory_id
        super().__init__(f"Memory {memory_id} not found")


class MemoryService:
    def __init__(self, conn: AsyncConnection):
        self._conn = conn

    async def store_memory(
        self,
        content: str,
        memory_type: MemoryType,
        user_id: UUID | None = None,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
    ) -> Memory:
        import json

        memory_id = uuid4()
        now = datetime.now(timezone.utc)
        metadata = metadata or {}
        embedding_str = json.dumps(embedding) if embedding else None
        metadata_str = json.dumps(metadata)

        await self._conn.execute(
            text(
                """
                INSERT INTO memories (id, user_id, content, embedding, metadata, memory_type, created_at, updated_at)
                VALUES (:id, :user_id, :content, :embedding, :metadata, :memory_type, :created_at, :updated_at)
                """
            ),
            {
                "id": str(memory_id),
                "user_id": str(user_id) if user_id else None,
                "content": content,
                "embedding": embedding_str,
                "metadata": metadata_str,
                "memory_type": memory_type.value,
                "created_at": now,
                "updated_at": now,
            },
        )

        return Memory(
            id=memory_id,
            user_id=user_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
            memory_type=memory_type,
            created_at=now,
            updated_at=now,
        )

    async def get_memory(self, memory_id: UUID) -> Memory:
        result = await self._conn.execute(
            text("SELECT * FROM memories WHERE id = :id"),
            {"id": str(memory_id)},
        )
        row = result.fetchone()

        if not row:
            raise MemoryNotFoundError(memory_id)

        return self._row_to_memory(row._mapping)

    async def delete_memory(self, memory_id: UUID) -> None:
        result = await self._conn.execute(
            text("DELETE FROM memories WHERE id = :id"),
            {"id": str(memory_id)},
        )

        if result.rowcount == 0:
            raise MemoryNotFoundError(memory_id)

    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        memory_type: MemoryType | None = None,
        user_id: UUID | None = None,
    ) -> list[Memory]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not query or len(query) > 1000:
            raise ValueError("query must be 1-1000 characters")

        conditions = ["content LIKE :query"]
        params: dict = {"query": f"%{query}%", "limit": limit}

        if memory_type:
            conditions.append("memory_type = :memory_type")
            params["memory_type"] = memory_type.value

        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = str(user_id)

        where_clause = " AND ".join(conditions)

        result = await self._conn.execute(
            text(
                f"""
                SELECT * FROM memories
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.fetchall()

        return [self._row_to_memory(row._mapping) for row in rows]

    async def get_memories_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
        user_id: UUID | None = None,
    ) -> list[Memory]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        if user_id:
            result = await self._conn.execute(
                text(
                    """
                    SELECT * FROM memories
                    WHERE memory_type = :memory_type AND user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"memory_type": memory_type.value, "user_id": str(user_id), "limit": limit},
            )
        else:
            result = await self._conn.execute(
                text(
                    """
                    SELECT * FROM memories
                    WHERE memory_type = :memory_type
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"memory_type": memory_type.value, "limit": limit},
            )
        rows = result.fetchall()

        return [self._row_to_memory(row._mapping) for row in rows]

    async def get_stats(self) -> MemoryStats:
        result = await self._conn.execute(text("SELECT COUNT(*) as cnt FROM memories"))
        total = result.fetchone()._mapping["cnt"]

        result = await self._conn.execute(
            text("SELECT memory_type, COUNT(*) as cnt FROM memories GROUP BY memory_type")
        )
        type_counts = result.fetchall()
        memories_by_type = {row._mapping["memory_type"]: row._mapping["cnt"] for row in type_counts}

        try:
            result = await self._conn.execute(
                text("SELECT COUNT(*) as cnt FROM conversation_sessions")
            )
            total_conversations = result.fetchone()._mapping["cnt"]
        except Exception:
            total_conversations = 0

        try:
            result = await self._conn.execute(text("SELECT COUNT(*) as cnt FROM task_patterns"))
            total_patterns = result.fetchone()._mapping["cnt"]
        except Exception:
            total_patterns = 0

        return MemoryStats(
            total_memories=total or 0,
            memories_by_type=memories_by_type,
            total_conversations=total_conversations or 0,
            total_patterns=total_patterns or 0,
            avg_embedding_dimensions=384,
        )

    def _row_to_memory(self, row: dict) -> Memory:
        import json

        embedding = None
        if row.get("embedding"):
            raw = row["embedding"]
            if isinstance(raw, str):
                try:
                    embedding = json.loads(raw)
                except (json.JSONDecodeError, ValueError, TypeError):
                    embedding = None
            elif isinstance(raw, list):
                embedding = raw

        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, ValueError, TypeError):
                metadata = {}

        return Memory(
            id=UUID(str(row["id"])) if isinstance(row["id"], str) else row["id"],
            user_id=UUID(str(row["user_id"])) if row.get("user_id") and isinstance(row["user_id"], str) else row.get("user_id"),
            content=row["content"],
            embedding=embedding,
            metadata=metadata,
            memory_type=MemoryType(row["memory_type"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
