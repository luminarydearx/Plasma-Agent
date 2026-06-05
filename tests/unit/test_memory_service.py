import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime
from plasmaagent.memory.models import Memory, MemoryType, MemoryStats
from plasmaagent.memory.service import MemoryService, MemoryNotFoundError


class MockAsyncCursor:
    def __init__(self):
        self.execute = AsyncMock()
        self.fetchone = AsyncMock()
        self.fetchall = AsyncMock()
        self.rowcount = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    mock_cursor = MockAsyncCursor()
    conn.cursor = MagicMock(return_value=mock_cursor)
    return conn, mock_cursor


@pytest.fixture
def memory_service(mock_conn):
    conn, _ = mock_conn
    return MemoryService(conn)


class TestStoreMemory:
    @pytest.mark.asyncio
    async def test_store_memory_minimal(self, memory_service, mock_conn):
        conn, _ = mock_conn
        memory = await memory_service.store_memory(
            content="Test memory",
            memory_type=MemoryType.FACT
        )

        assert memory.content == "Test memory"
        assert memory.memory_type == MemoryType.FACT
        assert memory.user_id is None
        assert memory.embedding is None
        assert memory.metadata == {}
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_memory_full(self, memory_service, mock_conn):
        user_id = uuid4()
        embedding = [0.1, 0.2, 0.3]
        metadata = {"key": "value"}

        memory = await memory_service.store_memory(
            content="Test memory",
            memory_type=MemoryType.CONVERSATION,
            user_id=user_id,
            metadata=metadata,
            embedding=embedding
        )

        assert memory.user_id == user_id
        assert memory.embedding == embedding
        assert memory.metadata == metadata
        assert memory.memory_type == MemoryType.CONVERSATION

    @pytest.mark.asyncio
    async def test_store_memory_with_embedding(self, memory_service, mock_conn):
        embedding = [0.1] * 384

        memory = await memory_service.store_memory(
            content="Test",
            memory_type=MemoryType.FACT,
            embedding=embedding
        )

        assert len(memory.embedding) == 384


class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_memory_success(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        memory_id = uuid4()
        now = datetime.now()
        mock_cursor.fetchone.return_value = (
            memory_id, None, 'Test memory', None, {}, 'fact', now, now
        )

        result = await memory_service.get_memory(memory_id)

        assert result.id == memory_id
        assert result.content == 'Test memory'
        assert result.memory_type == MemoryType.FACT

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchone.return_value = None
        memory_id = uuid4()

        with pytest.raises(MemoryNotFoundError) as exc_info:
            await memory_service.get_memory(memory_id)

        assert exc_info.value.memory_id == memory_id

    @pytest.mark.asyncio
    async def test_get_memory_with_embedding(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        memory_id = uuid4()
        now = datetime.now()
        mock_cursor.fetchone.return_value = (
            memory_id, None, 'Test', '[0.1, 0.2, 0.3]', {}, 'fact', now, now
        )

        result = await memory_service.get_memory(memory_id)

        assert result.embedding == [0.1, 0.2, 0.3]


class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_delete_memory_success(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.rowcount = 1
        memory_id = uuid4()

        await memory_service.delete_memory(memory_id)

        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_not_found(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.rowcount = 0
        memory_id = uuid4()

        with pytest.raises(MemoryNotFoundError):
            await memory_service.delete_memory(memory_id)


class TestSearchMemories:
    @pytest.mark.asyncio
    async def test_search_memories_basic(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        now = datetime.now()
        mock_cursor.fetchall.return_value = [
            (uuid4(), None, 'Test memory 1', None, {}, 'fact', now, now)
        ]

        results = await memory_service.search_memories("test")

        assert len(results) == 1
        assert results[0].content == 'Test memory 1'

    @pytest.mark.asyncio
    async def test_search_memories_with_type_filter(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []

        await memory_service.search_memories("test", memory_type=MemoryType.FACT)

        call_args = mock_cursor.execute.call_args
        assert 'memory_type = %s' in call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_memories_with_user_filter(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []
        user_id = uuid4()

        await memory_service.search_memories("test", user_id=user_id)

        call_args = mock_cursor.execute.call_args
        assert 'user_id = %s' in call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_memories_with_limit(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []

        await memory_service.search_memories("test", limit=5)

        call_args = mock_cursor.execute.call_args
        assert call_args[0][1][-1] == 5

    @pytest.mark.asyncio
    async def test_search_memories_empty_results(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []

        results = await memory_service.search_memories("nonexistent")

        assert results == []


class TestGetMemoriesByType:
    @pytest.mark.asyncio
    async def test_get_memories_by_type(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        now = datetime.now()
        mock_cursor.fetchall.return_value = [
            (uuid4(), None, 'Fact 1', None, {}, 'fact', now, now)
        ]

        results = await memory_service.get_memories_by_type(MemoryType.FACT)

        assert len(results) == 1
        assert results[0].memory_type == MemoryType.FACT

    @pytest.mark.asyncio
    async def test_get_memories_by_type_with_user(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []
        user_id = uuid4()

        await memory_service.get_memories_by_type(MemoryType.FACT, user_id=user_id)

        call_args = mock_cursor.execute.call_args
        assert 'user_id = %s' in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_memories_by_type_with_limit(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchall.return_value = []

        await memory_service.get_memories_by_type(MemoryType.FACT, limit=50)

        call_args = mock_cursor.execute.call_args
        assert call_args[0][1][-1] == 50


class TestGetStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchone.side_effect = [(0,), (0,), (0,)]
        mock_cursor.fetchall.return_value = []

        stats = await memory_service.get_stats()

        assert stats.total_memories == 0
        assert stats.memories_by_type == {}
        assert stats.total_conversations == 0
        assert stats.total_patterns == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchone.side_effect = [(100,), (10,), (5,)]
        mock_cursor.fetchall.return_value = [
            ('fact', 50),
            ('conversation', 50)
        ]

        stats = await memory_service.get_stats()

        assert stats.total_memories == 100
        assert stats.memories_by_type == {'fact': 50, 'conversation': 50}
        assert stats.total_conversations == 10
        assert stats.total_patterns == 5

    @pytest.mark.asyncio
    async def test_get_stats_none_values(self, memory_service, mock_conn):
        conn, mock_cursor = mock_conn
        mock_cursor.fetchone.side_effect = [(None,), (None,), (None,)]
        mock_cursor.fetchall.return_value = []

        stats = await memory_service.get_stats()

        assert stats.total_memories == 0
        assert stats.total_conversations == 0
        assert stats.total_patterns == 0
