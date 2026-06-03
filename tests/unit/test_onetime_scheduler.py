from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.scheduling.onetime import OneTimeScheduler
from plasmaagent.models.task import Task


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


class TestOneTimeScheduler:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def scheduler(self, mock_db):
        return OneTimeScheduler(mock_db)

    @pytest.fixture
    def sample_task(self):
        return Task(
            id=uuid4(),
            name="One-Time Task",
            description="Run once at specific time",
            status="PENDING",
            payload={"commands": ["echo hello"]},
            cron_expression=None,
            is_scheduled=True,
            next_run_at=datetime.now() + timedelta(hours=1),
            last_run_at=None,
            schedule_timezone=None,
            missed_run_policy="run_once",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_schedule_at_success(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        run_at = datetime.now() + timedelta(hours=2)
        result = await scheduler.schedule_at(sample_task.id, run_at, "UTC")

        assert result is not None
        assert result.id == sample_task.id
        assert result.missed_run_policy == "run_once"
        assert result.cron_expression is None
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_at_task_not_found(self, scheduler, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.schedule_at(uuid4(), datetime.now())

        assert result is None

    @pytest.mark.asyncio
    async def test_schedule_in_success(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.schedule_in(sample_task.id, 3600, "UTC")

        assert result is not None
        assert result.id == sample_task.id
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_in_negative_seconds(self, scheduler, mock_db):
        with pytest.raises(ValueError, match="seconds must be non-negative"):
            await scheduler.schedule_in(uuid4(), -100)

    @pytest.mark.asyncio
    async def test_schedule_in_zero_seconds(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.schedule_in(sample_task.id, 0)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_pending_one_time_tasks_empty(self, scheduler, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        result = await scheduler.get_pending_one_time_tasks(datetime.now())

        assert result == []
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_one_time_tasks_with_results(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await scheduler.get_pending_one_time_tasks(datetime.now())

        assert len(result) == 1
        assert result[0].id == sample_task.id
        assert result[0].missed_run_policy == "run_once"

    @pytest.mark.asyncio
    async def test_mark_completed_success(self, scheduler, mock_db, sample_task):
        completed_task = sample_task.model_copy(
            update={
                "last_run_at": datetime.now(),
                "next_run_at": None,
                "is_scheduled": False,
            }
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = completed_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.mark_completed(sample_task.id, datetime.now())

        assert result is not None
        assert result.is_scheduled is False
        assert result.next_run_at is None
        assert result.last_run_at is not None

    @pytest.mark.asyncio
    async def test_mark_completed_task_not_found(self, scheduler, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.mark_completed(uuid4(), datetime.now())

        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_schedule_success(self, scheduler, mock_db, sample_task):
        cancelled_task = sample_task.model_copy(
            update={"is_scheduled": False, "next_run_at": None}
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = cancelled_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.cancel_schedule(sample_task.id)

        assert result is not None
        assert result.is_scheduled is False
        assert result.next_run_at is None

    @pytest.mark.asyncio
    async def test_cancel_schedule_task_not_found(self, scheduler, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.cancel_schedule(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_reschedule_success(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        new_time = datetime.now() + timedelta(hours=3)
        result = await scheduler.reschedule(sample_task.id, new_time, "UTC")

        assert result is not None
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_at_with_timezone(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        run_at = datetime.now() + timedelta(hours=1)
        result = await scheduler.schedule_at(
            sample_task.id, run_at, "Asia/Jakarta"
        )

        assert result is not None
        call_args = mock_cursor.execute.call_args
        assert "Asia/Jakarta" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_schedule_in_large_delay(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.schedule_in(sample_task.id, 86400)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_pending_filters_by_policy(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await scheduler.get_pending_one_time_tasks(datetime.now())

        assert len(result) == 1
        call_args = mock_cursor.execute.call_args
        assert "run_once" in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_mark_completed_clears_schedule(self, scheduler, mock_db, sample_task):
        completed_task = sample_task.model_copy(
            update={
                "last_run_at": datetime.now(),
                "next_run_at": None,
                "is_scheduled": False,
            }
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = completed_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await scheduler.mark_completed(sample_task.id, datetime.now())

        assert result is not None
        assert result.next_run_at is None
        assert result.is_scheduled is False

    @pytest.mark.asyncio
    async def test_schedule_at_naive_datetime(self, scheduler, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        naive_dt = datetime.now() + timedelta(hours=1)
        result = await scheduler.schedule_at(sample_task.id, naive_dt)

        assert result is not None
