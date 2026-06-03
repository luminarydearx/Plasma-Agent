import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.scheduling.scheduler import SchedulerService


def make_mock_conn():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.execute = AsyncMock()
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=None)

    mock_conn = MagicMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    return mock_conn, mock_cursor


def make_scheduler(db=None, callback=None, interval=60):
    if db is None:
        mock_conn, _ = make_mock_conn()
        db = MagicMock()
        db.connection = MagicMock(return_value=mock_conn)
        db.transaction = MagicMock(return_value=mock_conn)
    return SchedulerService(
        db=db,
        execution_callback=callback,
        check_interval_seconds=interval,
    )


class TestSchedulerServiceInit:
    def test_default_interval(self):
        s = make_scheduler()
        assert s._check_interval == 60

    def test_custom_interval(self):
        s = make_scheduler(interval=30)
        assert s._check_interval == 30

    def test_minimum_interval(self):
        s = make_scheduler(interval=0)
        assert s._check_interval == 1

    def test_not_running_initially(self):
        s = make_scheduler()
        assert s.is_running is False


class TestSchedulerStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        s = make_scheduler()
        await s.start()
        try:
            assert s.is_running is True
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        s = make_scheduler()
        await s.start()
        await s.stop()
        assert s.is_running is False

    @pytest.mark.asyncio
    async def test_double_start_idempotent(self):
        s = make_scheduler()
        await s.start()
        await s.start()
        try:
            assert s.is_running is True
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_double_stop_idempotent(self):
        s = make_scheduler()
        await s.start()
        await s.stop()
        await s.stop()
        assert s.is_running is False

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        s = make_scheduler()
        await s.stop()
        assert s.is_running is False


class TestSchedulerTick:
    @pytest.mark.asyncio
    async def test_tick_no_due_tasks(self):
        mock_conn, mock_cursor = make_mock_conn()
        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)

        count = await s._tick()
        assert count == 0

    @pytest.mark.asyncio
    async def test_tick_executes_due_task(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                "id": task_id,
                "cron_expression": "* * * * *",
                "missed_run_policy": "skip",
                "last_run_at": None,
            }
        ])
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)

        callback_called = []
        async def callback(tid):
            callback_called.append(tid)
            return True

        s._execution_callback = callback

        count = await s._tick()
        assert count == 1
        assert callback_called == [task_id]

    @pytest.mark.asyncio
    async def test_tick_skips_locked_task(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                "id": task_id,
                "cron_expression": "* * * * *",
                "missed_run_policy": "skip",
                "last_run_at": None,
            }
        ])
        mock_cursor.fetchone = AsyncMock(return_value=None)

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)

        callback = AsyncMock()
        s._execution_callback = callback

        count = await s._tick()
        assert count == 0
        callback.assert_not_called()


class TestSchedulerExecution:
    @pytest.mark.asyncio
    async def test_execute_with_successful_callback(self):
        task_id = uuid4()
        callback = AsyncMock(return_value=True)
        s = make_scheduler(callback=callback)

        result = await s._execute_task(task_id)
        assert result is True
        callback.assert_awaited_once_with(task_id)

    @pytest.mark.asyncio
    async def test_execute_with_failing_callback(self):
        task_id = uuid4()
        callback = AsyncMock(return_value=False)
        s = make_scheduler(callback=callback)

        result = await s._execute_task(task_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_with_raising_callback(self):
        task_id = uuid4()
        callback = AsyncMock(side_effect=RuntimeError("boom"))
        s = make_scheduler(callback=callback)

        result = await s._execute_task(task_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_without_callback(self):
        task_id = uuid4()
        s = make_scheduler(callback=None)

        result = await s._execute_task(task_id)
        assert result is False


class TestSchedulerScheduling:
    @pytest.mark.asyncio
    async def test_schedule_task_sets_next_run(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        next_run = await s.schedule_task(task_id, "0 0 * * *")
        assert isinstance(next_run, datetime)
        assert next_run > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_schedule_task_special_expression(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        next_run = await s.schedule_task(task_id, "@daily")
        assert isinstance(next_run, datetime)

    @pytest.mark.asyncio
    async def test_schedule_task_invalid_cron(self):
        task_id = uuid4()
        s = make_scheduler()

        with pytest.raises(ValueError, match="5 fields"):
            await s.schedule_task(task_id, "invalid")

    @pytest.mark.asyncio
    async def test_schedule_task_not_found(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        with pytest.raises(ValueError, match="not found"):
            await s.schedule_task(task_id, "0 0 * * *")


class TestSchedulerUnschedule:
    @pytest.mark.asyncio
    async def test_unschedule_updates_db(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        await s.unschedule_task(task_id)
        mock_cursor.execute.assert_awaited()


class TestSchedulerGetScheduled:
    @pytest.mark.asyncio
    async def test_get_scheduled_returns_empty(self):
        mock_conn, mock_cursor = make_mock_conn()

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)

        result = await s.get_scheduled_tasks()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_scheduled_with_data(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                "id": task_id,
                "name": "test",
                "cron_expression": "* * * * *",
                "next_run_at": datetime.now(timezone.utc),
                "last_run_at": None,
                "status": "PENDING",
                "missed_run_policy": "skip",
            }
        ])

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)

        result = await s.get_scheduled_tasks()
        assert len(result) == 1
        assert result[0]["id"] == task_id


class TestSchedulerMissedExecutions:
    @pytest.mark.asyncio
    async def test_missed_skip_policy(self):
        task_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={
            "cron_expression": "0 * * * *",
            "missed_run_policy": "skip",
            "last_run_at": None,
            "next_run_at": past,
        })

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)

        count = await s.handle_missed_executions(task_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_missed_run_once_policy(self):
        task_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={
            "cron_expression": "0 * * * *",
            "missed_run_policy": "run_once",
            "last_run_at": None,
            "next_run_at": past,
        })

        callback = AsyncMock(return_value=True)
        s = make_scheduler(callback=callback)
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)

        count = await s.handle_missed_executions(task_id)
        assert count == 1
        callback.assert_awaited_once_with(task_id)

    @pytest.mark.asyncio
    async def test_missed_task_not_found(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)

        count = await s.handle_missed_executions(task_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_missed_no_miss_when_future(self):
        task_id = uuid4()
        future = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={
            "cron_expression": "0 * * * *",
            "missed_run_policy": "run_once",
            "last_run_at": None,
            "next_run_at": future,
        })

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)

        count = await s.handle_missed_executions(task_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_missed_run_all_policy_multiple(self):
        task_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=3)

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={
            "cron_expression": "0 * * * *",
            "missed_run_policy": "run_all",
            "last_run_at": None,
            "next_run_at": past,
        })

        callback = AsyncMock(return_value=True)
        s = make_scheduler(callback=callback)
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)

        count = await s.handle_missed_executions(task_id)
        assert count >= 2
        assert callback.await_count >= 2


class TestSchedulerEdgeCases:
    @pytest.mark.asyncio
    async def test_tick_handles_callback_exception(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                "id": task_id,
                "cron_expression": "* * * * *",
                "missed_run_policy": "skip",
                "last_run_at": None,
            }
        ])
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.connection = MagicMock(return_value=mock_conn)
        s._db.transaction = MagicMock(return_value=mock_conn)
        s._execution_callback = AsyncMock(side_effect=RuntimeError("boom"))

        count = await s._tick()
        assert count == 1

    @pytest.mark.asyncio
    async def test_schedule_task_with_timezone(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        next_run = await s.schedule_task(
            task_id,
            "0 0 * * *",
            timezone_name="Asia/Jakarta",
        )
        assert isinstance(next_run, datetime)

    @pytest.mark.asyncio
    async def test_schedule_task_with_policies(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone = AsyncMock(return_value={"id": task_id})

        s = make_scheduler()
        s._db.transaction = MagicMock(return_value=mock_conn)

        for policy in ["skip", "run_once", "run_all"]:
            next_run = await s.schedule_task(task_id, "0 0 * * *", missed_run_policy=policy)
            assert isinstance(next_run, datetime)

    @pytest.mark.asyncio
    async def test_scheduler_loop_cancellable(self):
        s = make_scheduler(interval=1)

        await s.start()
        await asyncio.sleep(0.1)
        await s.stop()

        assert s.is_running is False

    @pytest.mark.asyncio
    async def test_update_after_execution_with_invalid_cron(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        s = make_scheduler()

        await s._update_after_execution(
            mock_conn,
            task_id,
            "invalid cron",
            datetime.now(timezone.utc),
            True,
        )

        mock_cursor.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_after_execution_with_valid_cron(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        s = make_scheduler()

        await s._update_after_execution(
            mock_conn,
            task_id,
            "0 0 * * *",
            datetime.now(timezone.utc),
            True,
        )

        mock_cursor.execute.assert_awaited()
        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert params[0] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_update_after_execution_failure_status(self):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()

        s = make_scheduler()

        await s._update_after_execution(
            mock_conn,
            task_id,
            "0 0 * * *",
            datetime.now(timezone.utc),
            False,
        )

        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert params[0] == "FAILED"
