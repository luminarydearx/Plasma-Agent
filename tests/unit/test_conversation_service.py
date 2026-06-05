import pytest
from unittest.mock import MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from plasmaagent.memory.conversation_service import ConversationService, ConversationNotFoundError


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


def make_mock_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def session_id():
    return uuid4()


class TestConversationServiceCreateSession:
    async def test_create_session_success(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        session = await service.create_session(user_id, "Test Session")

        assert isinstance(session.id, UUID)
        assert session.user_id == user_id
        assert session.title == "Test Session"
        assert session.message_count == 0
        assert len(cursor.executed_queries) == 1

    async def test_create_session_no_title(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        session = await service.create_session(user_id)

        assert session.title is None
        assert session.message_count == 0


class TestConversationServiceGetSession:
    async def test_get_session_success(self, user_id, session_id):
        now = datetime.now(timezone.utc)
        row = {
            "id": session_id, "user_id": user_id, "title": "Test",
            "message_count": 5, "created_at": now, "updated_at": now
        }
        cursor = MockAsyncCursor(fetchone_result=row)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        session = await service.get_session(session_id)

        assert session.id == session_id
        assert session.user_id == user_id
        assert session.title == "Test"
        assert session.message_count == 5

    async def test_get_session_not_found(self, session_id):
        cursor = MockAsyncCursor(fetchone_result=None)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ConversationNotFoundError) as exc_info:
            await service.get_session(session_id)

        assert exc_info.value.session_id == session_id


class TestConversationServiceListSessions:
    async def test_list_sessions_success(self, user_id):
        now = datetime.now(timezone.utc)
        rows = [
            {"id": uuid4(), "user_id": user_id, "title": "Session 1", "message_count": 3, "created_at": now, "updated_at": now},
            {"id": uuid4(), "user_id": user_id, "title": "Session 2", "message_count": 5, "created_at": now, "updated_at": now},
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        sessions = await service.list_sessions(user_id)

        assert len(sessions) == 2
        assert sessions[0].title == "Session 1"
        assert sessions[1].title == "Session 2"

    async def test_list_sessions_empty(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        sessions = await service.list_sessions(user_id)

        assert len(sessions) == 0

    async def test_list_sessions_invalid_limit_zero(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.list_sessions(user_id, limit=0)

    async def test_list_sessions_invalid_limit_too_large(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.list_sessions(user_id, limit=1001)

    async def test_list_sessions_custom_limit(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        await service.list_sessions(user_id, limit=10)

        query, params = cursor.executed_queries[0]
        assert params == (user_id, 10)


class TestConversationServiceDeleteSession:
    async def test_delete_session_success(self, session_id):
        cursor = MockAsyncCursor(rowcount=1)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        await service.delete_session(session_id)

        query, params = cursor.executed_queries[0]
        assert "DELETE" in query
        assert params == (session_id,)

    async def test_delete_session_not_found(self, session_id):
        cursor = MockAsyncCursor(rowcount=0)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ConversationNotFoundError):
            await service.delete_session(session_id)


class TestConversationServiceAddMessage:
    async def test_add_message_user(self, user_id, session_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        msg = await service.add_message(session_id, user_id, "user", "Hello")

        assert isinstance(msg.id, UUID)
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.session_id == session_id
        assert len(cursor.executed_queries) == 2

    async def test_add_message_assistant(self, user_id, session_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        msg = await service.add_message(session_id, user_id, "assistant", "Hi there")

        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    async def test_add_message_updates_count(self, user_id, session_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        await service.add_message(session_id, user_id, "user", "Test")

        update_query, _ = cursor.executed_queries[1]
        assert "UPDATE" in update_query
        assert "message_count + 1" in update_query


class TestConversationServiceGetMessages:
    async def test_get_messages_success(self, user_id, session_id):
        now = datetime.now(timezone.utc)
        rows = [
            {"id": uuid4(), "user_id": user_id, "session_id": session_id, "role": "user", "content": "Hello", "created_at": now},
            {"id": uuid4(), "user_id": user_id, "session_id": session_id, "role": "assistant", "content": "Hi", "created_at": now},
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        messages = await service.get_messages(session_id)

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    async def test_get_messages_empty(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        messages = await service.get_messages(session_id)

        assert len(messages) == 0

    async def test_get_messages_invalid_limit_zero(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.get_messages(session_id, limit=0)

    async def test_get_messages_invalid_limit_too_large(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.get_messages(session_id, limit=1001)


class TestConversationServiceGetContext:
    async def test_get_context_success(self, user_id, session_id):
        now = datetime.now(timezone.utc)
        rows = [
            {"id": uuid4(), "user_id": user_id, "session_id": session_id, "role": "assistant", "content": "Latest", "created_at": now},
            {"id": uuid4(), "user_id": user_id, "session_id": session_id, "role": "user", "content": "Older", "created_at": now},
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        context = await service.get_context(session_id, max_messages=5)

        assert len(context) == 2
        assert context[0].content == "Older"
        assert context[1].content == "Latest"

    async def test_get_context_invalid_max_zero(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="max_messages must be between"):
            await service.get_context(session_id, max_messages=0)

    async def test_get_context_invalid_max_too_large(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        with pytest.raises(ValueError, match="max_messages must be between"):
            await service.get_context(session_id, max_messages=101)

    async def test_get_context_empty(self, session_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = ConversationService(conn)

        context = await service.get_context(session_id)

        assert len(context) == 0
