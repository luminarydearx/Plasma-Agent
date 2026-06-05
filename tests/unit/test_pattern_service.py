import pytest
from unittest.mock import MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from plasmaagent.memory.pattern_service import PatternService, PatternNotFoundError


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
def pattern_id():
    return uuid4()


def make_pattern_row(pattern_id=None, user_id=None, task_name="backup", commands=None, **kwargs):
    now = datetime.now(timezone.utc)
    return {
        "id": pattern_id or uuid4(),
        "user_id": user_id,
        "task_name": task_name,
        "commands": commands or ["cmd1"],
        "success_count": kwargs.get("success_count", 5),
        "avg_duration_ms": kwargs.get("avg_duration_ms", 1200.0),
        "confidence": kwargs.get("confidence", 0.9),
        "created_at": kwargs.get("created_at", now),
        "updated_at": kwargs.get("updated_at", now),
    }


class TestPatternServiceRecordPattern:
    async def test_record_pattern_success(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        pattern = await service.record_pattern(
            "backup_db",
            ["pg_dump plasmaagent > backup.sql"],
            user_id=user_id,
            duration_ms=1500.0,
            success=True
        )

        assert isinstance(pattern.id, UUID)
        assert pattern.task_name == "backup_db"
        assert pattern.commands == ["pg_dump plasmaagent > backup.sql"]
        assert pattern.success_count == 1
        assert pattern.confidence == 1.0
        assert pattern.avg_duration_ms == 1500.0

    async def test_record_pattern_failure(self, user_id):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        pattern = await service.record_pattern(
            "bad_task",
            ["rm -rf /"],
            user_id=user_id,
            success=False
        )

        assert pattern.success_count == 0
        assert pattern.confidence == 0.0

    async def test_record_pattern_no_user(self):
        cursor = MockAsyncCursor()
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        pattern = await service.record_pattern("test", ["echo test"])

        assert pattern.user_id is None


class TestPatternServiceGetPattern:
    async def test_get_pattern_success(self, pattern_id, user_id):
        row = make_pattern_row(pattern_id=pattern_id, user_id=user_id, task_name="backup")
        cursor = MockAsyncCursor(fetchone_result=row)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        pattern = await service.get_pattern(pattern_id)

        assert pattern.id == pattern_id
        assert pattern.task_name == "backup"
        assert pattern.commands == ["cmd1"]
        assert pattern.success_count == 5
        assert pattern.confidence == 0.9

    async def test_get_pattern_not_found(self, pattern_id):
        cursor = MockAsyncCursor(fetchone_result=None)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(PatternNotFoundError) as exc_info:
            await service.get_pattern(pattern_id)

        assert exc_info.value.pattern_id == pattern_id


class TestPatternServiceFindByTaskName:
    async def test_find_by_task_name_success(self, user_id):
        rows = [
            make_pattern_row(user_id=user_id, task_name="backup_db"),
            make_pattern_row(user_id=user_id, task_name="backup_files"),
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.find_by_task_name("backup", user_id=user_id)

        assert len(patterns) == 2
        assert "backup" in patterns[0].task_name

    async def test_find_by_task_name_no_user(self):
        rows = [make_pattern_row(task_name="backup_db")]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.find_by_task_name("backup")

        assert len(patterns) == 1

    async def test_find_by_task_name_empty(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.find_by_task_name("nonexistent", user_id=user_id)

        assert len(patterns) == 0

    async def test_find_by_task_name_invalid_limit_zero(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.find_by_task_name("test", user_id=user_id, limit=0)

    async def test_find_by_task_name_invalid_limit_too_large(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.find_by_task_name("test", user_id=user_id, limit=1001)

    async def test_find_by_task_name_empty_name(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(ValueError, match="task_name must be 1-200"):
            await service.find_by_task_name("")


class TestPatternServiceUpdateSuccess:
    async def test_update_success_increments_count(self, pattern_id, user_id):
        old_row = {"success_count": 5, "avg_duration_ms": 1200.0}
        updated_row = make_pattern_row(
            pattern_id=pattern_id, user_id=user_id,
            success_count=6, avg_duration_ms=1250.0, confidence=0.85
        )

        cursor = MockAsyncCursor()
        cursor._fetchone_results = [old_row, updated_row]
        cursor._idx = 0

        async def fetchone():
            result = cursor._fetchone_results[cursor._idx]
            cursor._idx += 1
            return result

        cursor.fetchone = fetchone
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        updated = await service.update_success(pattern_id, 1500.0, success=True)

        assert updated.success_count == 6
        assert updated.confidence > 0

    async def test_update_success_not_found(self, pattern_id):
        cursor = MockAsyncCursor(fetchone_result=None)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(PatternNotFoundError):
            await service.update_success(pattern_id, 1000.0)


class TestPatternServiceDeletePattern:
    async def test_delete_pattern_success(self, pattern_id):
        cursor = MockAsyncCursor(rowcount=1)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        await service.delete_pattern(pattern_id)

        query, params = cursor.executed_queries[0]
        assert "DELETE" in query
        assert params == (pattern_id,)

    async def test_delete_pattern_not_found(self, pattern_id):
        cursor = MockAsyncCursor(rowcount=0)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(PatternNotFoundError):
            await service.delete_pattern(pattern_id)


class TestPatternServiceGetTopPatterns:
    async def test_get_top_patterns_with_user(self, user_id):
        rows = [
            make_pattern_row(user_id=user_id, confidence=0.95, success_count=10),
            make_pattern_row(user_id=user_id, confidence=0.90, success_count=8),
        ]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.get_top_patterns(user_id=user_id, limit=10)

        assert len(patterns) == 2
        assert patterns[0].confidence >= patterns[1].confidence

    async def test_get_top_patterns_no_user(self):
        rows = [make_pattern_row(confidence=0.95)]
        cursor = MockAsyncCursor(fetchall_result=rows)
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.get_top_patterns(limit=5)

        assert len(patterns) == 1

    async def test_get_top_patterns_empty(self, user_id):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        patterns = await service.get_top_patterns(user_id=user_id)

        assert len(patterns) == 0

    async def test_get_top_patterns_invalid_limit_zero(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.get_top_patterns(limit=0)

    async def test_get_top_patterns_invalid_limit_too_large(self):
        cursor = MockAsyncCursor(fetchall_result=[])
        conn = make_mock_conn(cursor)
        service = PatternService(conn)

        with pytest.raises(ValueError, match="limit must be between"):
            await service.get_top_patterns(limit=101)
