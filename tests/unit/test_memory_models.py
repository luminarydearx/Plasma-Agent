import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError
from plasmaagent.memory.models import (
    MemoryType,
    Memory,
    ConversationMessage,
    ConversationSession,
    TaskPattern,
    MemorySearchResult,
    MemoryStats,
)


class TestMemoryType:
    def test_memory_type_values(self):
        assert MemoryType.CONVERSATION == "conversation"
        assert MemoryType.PATTERN == "pattern"
        assert MemoryType.FACT == "fact"
        assert MemoryType.PREFERENCE == "preference"
        assert MemoryType.TASK_RESULT == "task_result"

    def test_memory_type_is_string(self):
        assert isinstance(MemoryType.CONVERSATION.value, str)


class TestMemory:
    def test_create_memory_minimal(self):
        memory = Memory(
            id=uuid4(),
            content="Test memory",
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert memory.content == "Test memory"
        assert memory.memory_type == MemoryType.FACT
        assert memory.user_id is None
        assert memory.embedding is None
        assert memory.metadata == {}
        assert memory.similarity is None

    def test_create_memory_full(self):
        user_id = uuid4()
        embedding = [0.1] * 384
        memory = Memory(
            id=uuid4(),
            user_id=user_id,
            content="Test memory",
            embedding=embedding,
            metadata={"key": "value"},
            memory_type=MemoryType.CONVERSATION,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            similarity=0.95,
        )
        assert memory.user_id == user_id
        assert len(memory.embedding) == 384
        assert memory.metadata == {"key": "value"}
        assert memory.similarity == 0.95

    def test_memory_frozen(self):
        memory = Memory(
            id=uuid4(),
            content="Test",
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        with pytest.raises(ValidationError):
            memory.content = "Modified"

    def test_memory_empty_content_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="",
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_memory_content_too_long_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="x" * 10001,
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_memory_embedding_empty_list_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="Test",
                embedding=[],
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_memory_embedding_too_large_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="Test",
                embedding=[0.1] * 1537,
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_memory_embedding_valid(self):
        embedding = [0.1, 0.2, 0.3]
        memory = Memory(
            id=uuid4(),
            content="Test",
            embedding=embedding,
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert memory.embedding == embedding

    def test_memory_similarity_bounds(self):
        memory = Memory(
            id=uuid4(),
            content="Test",
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            similarity=0.5,
        )
        assert memory.similarity == 0.5

    def test_memory_similarity_negative_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="Test",
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                similarity=-0.1,
            )

    def test_memory_similarity_greater_than_one_fails(self):
        with pytest.raises(ValidationError):
            Memory(
                id=uuid4(),
                content="Test",
                memory_type=MemoryType.FACT,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                similarity=1.1,
            )


class TestConversationMessage:
    def test_create_message(self):
        msg = ConversationMessage(
            id=uuid4(),
            user_id=uuid4(),
            session_id=uuid4(),
            role="user",
            content="Hello",
            created_at=datetime.now(),
        )
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_invalid_role_fails(self):
        with pytest.raises(ValidationError):
            ConversationMessage(
                id=uuid4(),
                user_id=uuid4(),
                session_id=uuid4(),
                role="invalid",
                content="Hello",
                created_at=datetime.now(),
            )

    def test_message_valid_roles(self):
        for role in ["user", "assistant", "system"]:
            msg = ConversationMessage(
                id=uuid4(),
                user_id=uuid4(),
                session_id=uuid4(),
                role=role,
                content="Test",
                created_at=datetime.now(),
            )
            assert msg.role == role


class TestConversationSession:
    def test_create_session(self):
        session = ConversationSession(
            id=uuid4(),
            user_id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert session.title is None
        assert session.message_count == 0

    def test_session_with_title(self):
        session = ConversationSession(
            id=uuid4(),
            user_id=uuid4(),
            title="Debug session",
            message_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert session.title == "Debug session"
        assert session.message_count == 5


class TestTaskPattern:
    def test_create_pattern(self):
        pattern = TaskPattern(
            id=uuid4(),
            task_name="Backup database",
            commands=["pg_dump", "gzip"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert pattern.task_name == "Backup database"
        assert pattern.commands == ["pg_dump", "gzip"]
        assert pattern.success_count == 0
        assert pattern.confidence == 0.0

    def test_pattern_empty_commands_fails(self):
        with pytest.raises(ValidationError):
            TaskPattern(
                id=uuid4(),
                task_name="Test",
                commands=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_pattern_empty_command_string_fails(self):
        with pytest.raises(ValidationError):
            TaskPattern(
                id=uuid4(),
                task_name="Test",
                commands=["valid", ""],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_pattern_confidence_bounds(self):
        pattern = TaskPattern(
            id=uuid4(),
            task_name="Test",
            commands=["cmd"],
            confidence=0.85,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert pattern.confidence == 0.85

    def test_pattern_confidence_negative_fails(self):
        with pytest.raises(ValidationError):
            TaskPattern(
                id=uuid4(),
                task_name="Test",
                commands=["cmd"],
                confidence=-0.1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_pattern_confidence_greater_than_one_fails(self):
        with pytest.raises(ValidationError):
            TaskPattern(
                id=uuid4(),
                task_name="Test",
                commands=["cmd"],
                confidence=1.1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )


class TestMemorySearchResult:
    def test_create_result(self):
        memory = Memory(
            id=uuid4(),
            content="Test",
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        result = MemorySearchResult(memory=memory, similarity=0.92)
        assert result.memory == memory
        assert result.similarity == 0.92


class TestMemoryStats:
    def test_create_stats(self):
        stats = MemoryStats(
            total_memories=100,
            memories_by_type={"fact": 50, "conversation": 50},
            total_conversations=10,
            total_patterns=5,
        )
        assert stats.total_memories == 100
        assert stats.memories_by_type == {"fact": 50, "conversation": 50}

    def test_stats_defaults(self):
        stats = MemoryStats()
        assert stats.total_memories == 0
        assert stats.memories_by_type == {}
        assert stats.total_conversations == 0
        assert stats.total_patterns == 0
        assert stats.avg_embedding_dimensions == 384
