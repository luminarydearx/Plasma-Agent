"""Memory tools for PlasmaAgent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def store_memory(content: str, memory_type: str = "fact", metadata: dict[str, Any] | None = None) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService
        from plasmaagent.memory.models import MemoryType

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                mt = MemoryType(memory_type)
                memory = await service.store_memory(content, mt, metadata=metadata or {})
                await conn.commit()
                return ToolResult(True, f"Stored memory: {memory.id}", {"id": str(memory.id)})
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to store memory: {e}")


async def search_memory(query: str, limit: int = 10) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                memories = await service.search_memories(query, limit=limit)
                results = [
                    {
                        "id": str(m.id),
                        "content": m.content,
                        "type": m.memory_type.value,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in memories
                ]
                return ToolResult(
                    True,
                    f"Found {len(results)} memories",
                    {"memories": results},
                )
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to search memory: {e}")
