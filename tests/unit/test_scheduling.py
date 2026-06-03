import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from plasmaagent.scheduling.models import MissedRunPolicy, TaskScheduleUpdate
from plasmaagent.scheduling.service import SchedulingService
from plasmaagent.scheduling.worker import SchedulerWorker
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


class TestSchedulingService:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return SchedulingService(mock_db)

    @pytest.fixture
    def sample_task(self):
        return Task(
            id=uuid4(),
            name="Test Task",
            description="Test description",
            status="PENDING",
            payload={"commands": ["echo hello"]},
            cron_expression="* * * * *",
            is_scheduled=True,
            next_run_at=datetime.now() + timedelta(minutes=1),
            last_run_at=None,
            schedule_timezone=None,
            missed_run_policy="skip",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_enable_schedule_success(self, service, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await service.enable_schedule(
            sample_task.id,
            "0 * * * *",
            timezone="UTC",
            missed_run_policy=MissedRunPolicy.SKIP,
        )

        assert result is not None
        assert result.id == sample_task.id
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_schedule_invalid_cron(self, service, mock_db):
        with pytest.raises(ValueError):
            await service.enable_schedule(uuid4(), "invalid cron")

    @pytest.mark.asyncio
    async def test_disable_schedule_success(self, service, mock_db, sample_task):
        disabled_task = sample_task.model_copy(update={"is_scheduled": False, "next_run_at": None})

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = disabled_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await service.disable_schedule(sample_task.id)

        assert result is not None
        assert result.is_scheduled is False
        assert result.next_run_at is None

    @pytest.mark.asyncio
    async def test_update_schedule_partial(self, service, mock_db, sample_task):
        updated_task = sample_task.model_copy(
            update={"schedule_timezone": "Asia/Jakarta"}
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = updated_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await service.update_schedule(
            sample_task.id,
            TaskScheduleUpdate(schedule_timezone="Asia/Jakarta"),
        )

        assert result is not None
        assert result.schedule_timezone == "Asia/Jakarta"

    @pytest.mark.asyncio
    async def test_get_due_tasks_empty(self, service, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        result = await service.get_due_tasks(datetime.now())

        assert result == []
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_due_tasks_with_results(self, service, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.get_due_tasks(datetime.now())

        assert len(result) == 1
        assert result[0].id == sample_task.id

    @pytest.mark.asyncio
    async def test_mark_executed_updates_timestamps(self, service, mock_db, sample_task):
        executed_at = datetime.now()
        next_run = executed_at + timedelta(hours=1)
        updated_task = sample_task.model_copy(
            update={"last_run_at": executed_at, "next_run_at": next_run}
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = updated_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        result = await service.mark_executed(sample_task.id, executed_at, next_run)

        assert result is not None
        assert result.last_run_at == executed_at
        assert result.next_run_at == next_run

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_with_filter(self, service, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.list_scheduled_tasks(is_scheduled=True, limit=10, offset=0)

        assert len(result) == 1
        assert result[0].is_scheduled is True

    @pytest.mark.asyncio
    async def test_get_task_success(self, service, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.connection.return_value = mock_conn

        result = await service.get_task(sample_task.id)

        assert result is not None
        assert result.id == sample_task.id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, service, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = None
        mock_db.connection.return_value = mock_conn

        result = await service.get_task(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_scheduled_tasks_no_filter(self, service, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.list_scheduled_tasks(limit=10, offset=0)

        assert len(result) == 1


class TestSchedulerWorker:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_executor(self):
        return AsyncMock()

    @pytest.fixture
    def worker(self, mock_db, mock_executor):
        return SchedulerWorker(
            db=mock_db,
            task_executor=mock_executor,
            check_interval=1,
            max_concurrent=5,
        )

    @pytest.fixture
    def sample_task(self):
        return Task(
            id=uuid4(),
            name="Scheduled Task",
            description="Test",
            status="PENDING",
            payload={"commands": ["echo test"]},
            cron_expression="* * * * *",
            is_scheduled=True,
            next_run_at=datetime.now(),
            last_run_at=None,
            schedule_timezone=None,
            missed_run_policy="skip",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_worker_start_stop(self, worker, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        async def run_worker():
            await worker.start()

        task = asyncio.create_task(run_worker())
        await asyncio.sleep(0.1)

        assert worker.is_running is True

        await worker.stop()
        await asyncio.sleep(0.2)

        assert worker.is_running is False
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_executes_due_tasks(self, worker, mock_db, mock_executor, sample_task):
        worker._service.get_due_tasks = AsyncMock(return_value=[sample_task])
        worker._service.mark_executed = AsyncMock(return_value=sample_task)

        await worker._check_and_execute()

        await asyncio.sleep(0.2)

        mock_executor.assert_called_once_with(sample_task)
        worker._service.mark_executed.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_handles_executor_error(self, worker, mock_db, mock_executor, sample_task):
        mock_executor.side_effect = Exception("Execution failed")
        worker._service.get_due_tasks = AsyncMock(return_value=[sample_task])
        worker._service.mark_executed = AsyncMock(return_value=sample_task)

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_respects_concurrency_limit(self, worker, mock_db, mock_executor, sample_task):
        tasks = [
            sample_task.model_copy(update={"id": uuid4()})
            for _ in range(10)
        ]

        async def slow_executor(task):
            await asyncio.sleep(0.5)

        mock_executor.side_effect = slow_executor
        worker._service.get_due_tasks = AsyncMock(return_value=tasks)
        worker._service.mark_executed = AsyncMock()

        await worker._check_and_execute()
        await asyncio.sleep(0.1)

        assert worker.active_task_count <= worker._max_concurrent

        await asyncio.sleep(0.6)

    @pytest.mark.asyncio
    async def test_worker_skips_already_running_tasks(self, worker, mock_db, mock_executor, sample_task):
        async def slow_executor(task):
            await asyncio.sleep(1)

        mock_executor.side_effect = slow_executor
        worker._service.get_due_tasks = AsyncMock(return_value=[sample_task])
        worker._service.mark_executed = AsyncMock()

        await worker._check_and_execute()
        await asyncio.sleep(0.1)

        await worker._check_and_execute()
        await asyncio.sleep(0.1)

        assert mock_executor.call_count == 1

        await asyncio.sleep(1.1)

    @pytest.mark.asyncio
    async def test_worker_catch_up_policy(self, worker, mock_db, mock_executor, sample_task):
        task_with_catch_up = sample_task.model_copy(
            update={"missed_run_policy": "catch_up"}
        )

        mock_executor.side_effect = Exception("Failed")
        worker._service.get_due_tasks = AsyncMock(return_value=[task_with_catch_up])
        worker._service.mark_executed = AsyncMock(return_value=task_with_catch_up)

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        assert worker._service.mark_executed.call_count == 1

    @pytest.mark.asyncio
    async def test_worker_no_due_tasks(self, worker, mock_db, mock_executor):
        worker._service.get_due_tasks = AsyncMock(return_value=[])

        await worker._check_and_execute()

        mock_executor.assert_not_called()

    @pytest.mark.asyncio
    async def test_worker_multiple_tasks_sequential(self, worker, mock_db, mock_executor, sample_task):
        task1 = sample_task.model_copy(update={"id": uuid4(), "name": "Task 1"})
        task2 = sample_task.model_copy(update={"id": uuid4(), "name": "Task 2"})

        mock_executor.side_effect = [None, None]
        worker._service.get_due_tasks = AsyncMock(side_effect=[[task1], [task2], []])
        worker._service.mark_executed = AsyncMock()

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        assert mock_executor.call_count == 2

    @pytest.mark.asyncio
    async def test_worker_updates_next_run_after_execution(self, worker, mock_db, mock_executor, sample_task):
        worker._service.get_due_tasks = AsyncMock(return_value=[sample_task])
        worker._service.mark_executed = AsyncMock(return_value=sample_task)

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        worker._service.mark_executed.assert_called_once()
        call_args = worker._service.mark_executed.call_args
        assert call_args[0][0] == sample_task.id
        assert call_args[0][1] is not None

    @pytest.mark.asyncio
    async def test_worker_properties(self, worker):
        assert worker.is_running is False
        assert worker.active_task_count == 0

    @pytest.mark.asyncio
    async def test_worker_stop_when_not_running(self, worker):
        await worker.stop()

        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_start_twice(self, worker, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        async def run_worker():
            await worker.start()

        task = asyncio.create_task(run_worker())
        await asyncio.sleep(0.1)

        await worker.start()

        await worker.stop()
        await asyncio.sleep(0.1)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
