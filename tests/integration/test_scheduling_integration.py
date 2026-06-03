import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.scheduling import (
    SchedulingService,
    SchedulerWorker,
    OneTimeScheduler,
    RecurringPatterns,
    DependencyService,
    SchedulerPersistence,
    TaskDependencyCreate,
    DependencyType,
)
from plasmaagent.scheduling.cron_parser import CronParser
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


class TestSchedulingIntegration:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def sample_task(self):
        return Task(
            id=uuid4(),
            name="Integration Test Task",
            description="Test task for integration",
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
    async def test_full_scheduling_workflow(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()

        updated_task = sample_task.model_copy(
            update={"cron_expression": "0 9 * * *"}
        )
        mock_cursor.fetchone.return_value = updated_task.model_dump()
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        service = SchedulingService(mock_db)

        result = await service.enable_schedule(
            task_id=sample_task.id,
            cron_expression="0 9 * * *",
            timezone="UTC",
        )

        assert result is not None
        assert result.cron_expression == "0 9 * * *"

        tasks = await service.get_due_tasks(datetime.now())
        assert isinstance(tasks, list)

    @pytest.mark.asyncio
    async def test_one_time_to_recurring_transition(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        onetime = OneTimeScheduler(mock_db)
        result = await onetime.schedule_in(sample_task.id, 3600)
        assert result is not None

        service = SchedulingService(mock_db)
        recurring = await service.enable_schedule(
            sample_task.id,
            RecurringPatterns.daily(hour=9),
        )
        assert recurring is not None

    @pytest.mark.asyncio
    async def test_dependency_chain_execution(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()

        task_a = sample_task.model_copy(update={"id": uuid4(), "name": "Task A"})
        task_b = sample_task.model_copy(update={"id": uuid4(), "name": "Task B"})
        task_c = sample_task.model_copy(update={"id": uuid4(), "name": "Task C"})

        from plasmaagent.scheduling.dependencies import TaskDependency

        dep_ab = TaskDependency(
            id=uuid4(),
            source_task_id=task_a.id,
            target_task_id=task_b.id,
            dependency_type=DependencyType.ON_SUCCESS,
            created_at=datetime.now(),
        )

        dep_bc = TaskDependency(
            id=uuid4(),
            source_task_id=task_b.id,
            target_task_id=task_c.id,
            dependency_type=DependencyType.ON_SUCCESS,
            created_at=datetime.now(),
        )

        mock_cursor.fetchone.side_effect = [
            dep_ab.model_dump(),
            dep_bc.model_dump(),
        ]
        mock_cursor.fetchall.return_value = []
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        dep_service = DependencyService(mock_db)

        dep_ab_data = TaskDependencyCreate(
            source_task_id=task_a.id,
            target_task_id=task_b.id,
            dependency_type=DependencyType.ON_SUCCESS,
        )
        await dep_service.create_dependency(dep_ab_data)

        dep_bc_data = TaskDependencyCreate(
            source_task_id=task_b.id,
            target_task_id=task_c.id,
            dependency_type=DependencyType.ON_SUCCESS,
        )
        await dep_service.create_dependency(dep_bc_data)

        ready = await dep_service.get_tasks_ready_to_run()
        assert isinstance(ready, list)

    @pytest.mark.asyncio
    async def test_scheduler_persistence_recovery(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()

        from plasmaagent.scheduling.state import SchedulerState

        state = SchedulerState(
            id=uuid4(),
            is_running=True,
            last_check_at=datetime.now(),
            active_task_count=5,
            metadata={"test": "value"},
            updated_at=datetime.now(),
        )

        mock_cursor.fetchone.return_value = state.model_dump()
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        persistence = SchedulerPersistence(mock_db)

        saved = await persistence.save_state(
            is_running=True,
            last_check_at=datetime.now(),
            active_task_count=5,
            metadata={"test": "value"},
        )
        assert saved is not None

        recovery = await persistence.get_recovery_info()
        assert recovery["needs_recovery"] is True
        assert recovery["active_tasks"] == 5

    @pytest.mark.asyncio
    async def test_worker_basic_execution(self, mock_db, sample_task):
        mock_executor = AsyncMock()

        worker = SchedulerWorker(
            db=mock_db,
            task_executor=mock_executor,
            check_interval=1,
        )

        worker._service.get_due_tasks = AsyncMock(return_value=[sample_task])
        worker._service.mark_executed = AsyncMock(return_value=sample_task)

        await worker._check_and_execute()
        await asyncio.sleep(0.2)

        assert mock_executor.call_count == 1

    @pytest.mark.asyncio
    async def test_recurring_patterns_integration(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        patterns = [
            RecurringPatterns.hourly(minute=30),
            RecurringPatterns.daily(hour=9, minute=0),
            RecurringPatterns.weekly(day_of_week=1, hour=10),
            RecurringPatterns.weekdays(hour=8),
        ]

        service = SchedulingService(mock_db)

        for pattern in patterns:
            cron_expr = CronParser.parse(pattern)
            assert cron_expr is not None

            result = await service.enable_schedule(
                sample_task.id,
                pattern,
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_concurrent_schedule_checks(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_task.model_dump()]
        mock_db.connection.return_value = mock_conn

        service = SchedulingService(mock_db)

        tasks = await asyncio.gather(
            service.get_due_tasks(datetime.now()),
            service.get_due_tasks(datetime.now()),
            service.get_due_tasks(datetime.now()),
        )

        assert len(tasks) == 3
        assert all(isinstance(t, list) for t in tasks)

    @pytest.mark.asyncio
    async def test_schedule_with_timezone(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn

        service = SchedulingService(mock_db)

        result = await service.enable_schedule(
            sample_task.id,
            "0 9 * * *",
            timezone="Asia/Jakarta",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_missed_run_policies(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_db.transaction.return_value = mock_conn

        service = SchedulingService(mock_db)

        for policy in ["skip", "run_once", "run_all"]:
            task = sample_task.model_copy(
                update={"id": uuid4(), "missed_run_policy": policy}
            )
            mock_cursor.fetchone.return_value = task.model_dump()

            result = await service.enable_schedule(
                task.id,
                "0 9 * * *",
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_schedule_lifecycle(self, mock_db, sample_task):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_task.model_dump()
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        service = SchedulingService(mock_db)

        created = await service.enable_schedule(
            sample_task.id,
            "0 9 * * *",
        )
        assert created is not None

        disabled = await service.disable_schedule(sample_task.id)
        assert disabled is not None

        enabled = await service.enable_schedule(
            sample_task.id,
            "0 10 * * *",
        )
        assert enabled is not None

        executed = await service.mark_executed(
            sample_task.id,
            datetime.now(),
            datetime.now() + timedelta(days=1),
        )
        assert executed is not None
