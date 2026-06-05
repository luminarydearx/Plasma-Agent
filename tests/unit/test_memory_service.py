import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from plasmaagent.memory.service import MemoryService, MemoryNotFoundError
from plasmaagent.memory.models import Memory, MemoryType


class MockAsyncCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None, rowcount=1):
        self._fetchone_result = fetchone_result
        self._fetchall_result = fetchall_result if fetchall_result is not None else []
        self.rowcount = rowcount
        self.executed_queries = []

    async def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    async def fetchone(self):
        return self._fetchone_result

    async def fetchall(self):
        return self._fetchall_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def make_mock_conn(cursor=None):
    conn = MagicMock()
    conn.cursor.return_value = cursor or MockAsyncCursor()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()
    return conn


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def memory_id():
    return uuid4()


class TestMemoryServiceStore:
    async def test_store_memory_basic(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        memory = await service.store_memory(
            "Test content",
            MemoryType.FACT,
            user_id=user_id
        )

        assert isinstance(memory.id, UUID)
        assert memory.content == "Test content"
        assert memory.memory_type == MemoryType.FACT
        assert memory.user_id == user_id
        assert conn.execute.call_count == 1

    async def test_store_memory_with_metadata(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        memory = await service.store_memory(
            "Test with metadata",
            MemoryType.PREFERENCE,
            user_id=user_id,
            metadata={"source": "test", "priority": "high"}
        )

        assert memory.metadata == {"source": "test", "priority": "high"}

    async def test_store_memory_with_embedding(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        embedding = [0.1, 0.2, 0.3]
        memory = await service.store_memory(
            "Test with embedding",
            MemoryType.FACT,
            user_id=user_id,
            embedding=embedding
        )

        assert memory.embedding == embedding


class TestMemoryServiceGet:
    async def test_get_memory_success(self, memory_id, user_id):
        now = datetime.now(timezone.utc)
        row = {
            "id": memory_id,
            "user_id": user_id,
            "content": "Test content",
            "embedding": None,
            "metadata": {"key": "value"},
            "memory_type": "fact",
            "created_at": now,
            "updated_at": now
        }
        cursor = MockAsyncCursor(fetchone_result=row)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        memory = await service.get_memory(memory_id)

        assert memory.id == memory_id
        assert memory.content == "Test content"
        assert memory.metadata == {"key": "value"}

    async def test_get_memory_not_found(self, memory_id):
        cursor = MockAsyncCursor(fetchone_result=None)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(MemoryNotFoundError):
            await service.get_memory(memory_id)


class TestMemoryServiceDelete:
    async def test_delete_memory_success(self, memory_id):
        cursor = MockAsyncCursor(rowcount=1)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        await service.delete_memory(memory_id)

        query, params = cursor.executed_queries[0]
        assert "DELETE" in query

    async def test_delete_memory_not_found(self, memory_id):
        cursor = MockAsyncCursor(rowcount=0)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(MemoryNotFoundError):
            await service.delete_memory(memory_id)


class TestMemoryServiceSearch:
    async def test_search_memories_success(self, user_id):
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": uuid4(), "user_id": user_id, "content": "Test 1",
                "embedding": None, "metadata": {}, "memory_type": "fact",
                "created_at": now, "updated_at": now
            },
            {
                "id": uuid4(), "user_id": user_id, "content": "Test 2",
                "embedding": None, "metadata": {}, "memory_type": "fact",
                "created_at": now, "updated_at": now
            },
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        results = await service.search_memories("Test")

        assert len(results) == 2

    async def test_search_memories_empty(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        results = await service.search_memories("nonexistent")

        assert len(results) == 0

    async def test_search_memories_invalid_limit_zero(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.search_memories("test", limit=0)

    async def test_search_memories_invalid_limit_too_large(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.search_memories("test", limit=1001)

    async def test_search_memories_empty_query(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(ValueError, match="query must be"):
            await service.search_memories("")


class TestMemoryServiceGetByType:
    async def test_get_memories_by_type(self, user_id):
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": uuid4(), "user_id": user_id, "content": "Fact 1",
                "embedding": None, "metadata": {}, "memory_type": "fact",
                "created_at": now, "updated_at": now
            }
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        results = await service.get_memories_by_type(MemoryType.FACT)

        assert len(results) == 1

    async def test_get_memories_by_type_invalid_limit(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.get_memories_by_type(MemoryType.FACT, limit=0)


class TestMemoryServiceStats:
    async def test_get_stats(self):
        cursor = MockAsyncCursor()
        cursor._call_idx = 0
        cursor._fetchone_results = [
            {"cnt": 10},
            {"cnt": 3},
            {"cnt": 7},
        ]
        cursor._fetchall_results = [
            [{"memory_type": "fact", "cnt": 5}, {"memory_type": "pattern", "cnt": 5}],
        ]

        async def smart_fetchone():
            idx = cursor._call_idx
            cursor._call_idx += 1
            return cursor._fetchone_results[idx]

        async def smart_fetchall():
            return cursor._fetchall_results[0]

        cursor.fetchone = smart_fetchone
        cursor.fetchall = smart_fetchall

        conn = make_mock_conn(cursor)
        service = MemoryService(conn)

        stats = await service.get_stats()

        assert stats.total_memories == 10
        assert stats.total_conversations == 3
        assert stats.total_patterns == 7
        assert stats.memories_by_type["fact"] == 5
