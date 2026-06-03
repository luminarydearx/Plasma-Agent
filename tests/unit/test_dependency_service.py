from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.scheduling.dependencies import (
    DependencyType,
    TaskDependency,
    TaskDependencyCreate,
)
from plasmaagent.scheduling.dependency_service import DependencyService


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


class TestDependencyService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return DependencyService(mock_db)

    @pytest.fixture
    def sample_dependency(self):
        return TaskDependency(
            id=uuid4(),
            source_task_id=uuid4(),
            target_task_id=uuid4(),
            dependency_type=DependencyType.ON_SUCCESS,
            created_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_create_dependency_success(self, service, mock_db, sample_dependency):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = sample_dependency.model_dump()
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        data = TaskDependencyCreate(
            source_task_id=sample_dependency.source_task_id,
            target_task_id=sample_dependency.target_task_id,
            dependency_type=DependencyType.ON_SUCCESS,
        )

        result = await service.create_dependency(data)

        assert result is not None
        assert result.id == sample_dependency.id
        mock_cursor.execute.assert_called()

    @pytest.mark.asyncio
    async def test_create_dependency_self_reference(self, service, mock_db):
        task_id = uuid4()
        data = TaskDependencyCreate(
            source_task_id=task_id,
            target_task_id=task_id,
            dependency_type=DependencyType.ON_SUCCESS,
        )

        with pytest.raises(ValueError, match="Task cannot depend on itself"):
            await service.create_dependency(data)

    @pytest.mark.asyncio
    async def test_get_dependencies_for_task(self, service, mock_db, sample_dependency):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_dependency.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.get_dependencies_for_task(sample_dependency.target_task_id)

        assert len(result) == 1
        assert result[0].id == sample_dependency.id

    @pytest.mark.asyncio
    async def test_get_dependent_tasks(self, service, mock_db, sample_dependency):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_dependency.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.get_dependent_tasks(sample_dependency.source_task_id)

        assert len(result) == 1
        assert result[0].id == sample_dependency.id

    @pytest.mark.asyncio
    async def test_delete_dependency_success(self, service, mock_db, sample_dependency):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 1
        mock_db.transaction.return_value = mock_conn

        result = await service.delete_dependency(sample_dependency.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_dependency_not_found(self, service, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.rowcount = 0
        mock_db.transaction.return_value = mock_conn

        result = await service.delete_dependency(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_list_all_dependencies(self, service, mock_db, sample_dependency):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [sample_dependency.model_dump()]
        mock_db.connection.return_value = mock_conn

        result = await service.list_all_dependencies(limit=10, offset=0)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dependency_types(self):
        assert DependencyType.ON_SUCCESS.value == "on_success"
        assert DependencyType.ON_FAILURE.value == "on_failure"
        assert DependencyType.ON_COMPLETE.value == "on_complete"

    @pytest.mark.asyncio
    async def test_get_tasks_ready_to_run_empty(self, service, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        result = await service.get_tasks_ready_to_run()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_tasks_ready_to_run_with_results(self, service, mock_db):
        task_id = uuid4()
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = [{"target_task_id": task_id}]
        mock_db.connection.return_value = mock_conn

        result = await service.get_tasks_ready_to_run()

        assert len(result) == 1
        assert result[0] == task_id

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, service, mock_db):
        task_a = uuid4()
        task_b = uuid4()
        task_c = uuid4()

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.side_effect = [
            [{"target_task_id": task_c}],
            [{"target_task_id": task_a}],
            [],
        ]
        mock_db.connection.return_value = mock_conn

        result = await service._has_circular_dependency(task_a, task_b)

        assert result is True

    @pytest.mark.asyncio
    async def test_no_circular_dependency(self, service, mock_db):
        task_a = uuid4()
        task_b = uuid4()

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        result = await service._has_circular_dependency(task_a, task_b)

        assert result is False

    @pytest.mark.asyncio
    async def test_create_dependency_with_failure_type(self, service, mock_db, sample_dependency):
        failure_dep = sample_dependency.model_copy(
            update={"dependency_type": DependencyType.ON_FAILURE}
        )

        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchone.return_value = failure_dep.model_dump()
        mock_db.transaction.return_value = mock_conn
        mock_db.connection.return_value = mock_conn

        data = TaskDependencyCreate(
            source_task_id=failure_dep.source_task_id,
            target_task_id=failure_dep.target_task_id,
            dependency_type=DependencyType.ON_FAILURE,
        )

        result = await service.create_dependency(data)

        assert result is not None
        assert result.dependency_type == DependencyType.ON_FAILURE

    @pytest.mark.asyncio
    async def test_get_dependencies_empty(self, service, mock_db):
        mock_conn, mock_cursor = make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_db.connection.return_value = mock_conn

        result = await service.get_dependencies_for_task(uuid4())

        assert result == []
