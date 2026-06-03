from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.scheduling.persistence import SchedulerPersistence
from plasmaagent.scheduling.state import SchedulerState


def make_mock_conn():
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchone = AsyncMock()
    mock_cursor.fetchall = AsyncMock()
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    return mock_conn, mock_cursor


class TestSchedulerPersistence:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def persistence(self, mock_db):
        return SchedulerPersistence(mock_db)

    @pytest.fixture
    def sample_state(self):
        return SchedulerState(
            id=uuid4(),
            is_running=True,
            last_check_at=datetime.now(),
            active_task_count=5,
            metadata={"test": "value"},
            updated_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_save_state_success(self, persistence, mock_db, sample_state):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_state.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await persistence.save_state(
            is_running=True,
            last_check_at=datetime.now(),
            active_task_count=5,
            metadata={"test": "value"},
        )

        assert result is not None
        assert result.is_running is True
        assert result.active_task_count == 5
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_state_with_defaults(self, persistence, mock_db, sample_state):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_state.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await persistence.save_state(is_running=False)

        assert result is not None
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_state_success(self, persistence, mock_db, sample_state):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_state.model_dump()
        mock_db.connection.return_value = mock_conn

        result = await persistence.load_state()

        assert result is not None
        assert result.id == sample_state.id
        assert result.is_running == sample_state.is_running

    @pytest.mark.asyncio
    async def test_load_state_empty(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.connection.return_value = mock_conn

        result = await persistence.load_state()

        assert result is None

    @pytest.mark.asyncio
    async def test_clear_state(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_db.transaction.return_value = mock_conn

        result = await persistence.clear_state()

        assert result is True
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_last_check_success(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 1
        mock_db.transaction.return_value = mock_conn

        result = await persistence.update_last_check(datetime.now())

        assert result is True

    @pytest.mark.asyncio
    async def test_update_last_check_no_state(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 0
        mock_db.transaction.return_value = mock_conn

        result = await persistence.update_last_check(datetime.now())

        assert result is False

    @pytest.mark.asyncio
    async def test_update_active_tasks_success(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 1
        mock_db.transaction.return_value = mock_conn

        result = await persistence.update_active_tasks(10)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_active_tasks_no_state(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 0
        mock_db.transaction.return_value = mock_conn

        result = await persistence.update_active_tasks(10)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_recovery_info_with_state(self, persistence, mock_db, sample_state):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_state.model_dump()
        mock_db.connection.return_value = mock_conn

        result = await persistence.get_recovery_info()

        assert result["needs_recovery"] is True
        assert result["was_running"] is True
        assert result["active_tasks"] == 5

    @pytest.mark.asyncio
    async def test_get_recovery_info_no_state(self, persistence, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.connection.return_value = mock_conn

        result = await persistence.get_recovery_info()

        assert result["needs_recovery"] is False
        assert result["was_running"] is False
        assert result["active_tasks"] == 0

    @pytest.mark.asyncio
    async def test_get_recovery_info_stopped_state(self, persistence, mock_db, sample_state):
        stopped_state = sample_state.model_copy(update={"is_running": False})

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = stopped_state.model_dump()
        mock_db.connection.return_value = mock_conn

        result = await persistence.get_recovery_info()

        assert result["needs_recovery"] is False
        assert result["was_running"] is False

    @pytest.mark.asyncio
    async def test_save_state_with_metadata(self, persistence, mock_db, sample_state):
        metadata = {"key1": "value1", "key2": 123, "key3": [1, 2, 3]}

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_state.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await persistence.save_state(
            is_running=True,
            metadata=metadata,
        )

        assert result is not None
        mock_cursor.execute.assert_called_once()
