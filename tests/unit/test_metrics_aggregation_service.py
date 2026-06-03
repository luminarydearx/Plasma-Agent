from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from plasmaagent.observability.metrics_service import MetricsAggregationService
from plasmaagent.observability.models import (
    ExecutionMetrics,
    MetricsQuery,
    TimeRange,
)


def _make_mock_db(rows_by_query: list[tuple[str, Any]]) -> MagicMock:
    mock_db = MagicMock()
    call_index = {"i": 0}

    mock_cursor = AsyncMock()

    async def _execute_side_effect(sql: str, params: tuple | None = None) -> None:
        idx = call_index["i"]
        if idx < len(rows_by_query):
            mock_cursor._current_rows = rows_by_query[idx][1]
        call_index["i"] += 1

    async def _fetchone() -> Any:
        rows = getattr(mock_cursor, "_current_rows", None)
        if rows is None or len(rows) == 0:
            return None
        return rows[0]

    async def _fetchall() -> list[Any]:
        rows = getattr(mock_cursor, "_current_rows", None)
        return list(rows) if rows else []

    mock_cursor.execute = AsyncMock(side_effect=_execute_side_effect)
    mock_cursor.fetchone = AsyncMock(side_effect=_fetchone)
    mock_cursor.fetchall = AsyncMock(side_effect=_fetchall)
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)

    @asynccontextmanager
    async def _connection() -> AsyncIterator[MagicMock]:
        yield mock_conn

    mock_db.connection = _connection
    return mock_db


class TestMetricsAggregationServiceInit:
    def test_init_with_explicit_db(self) -> None:
        mock_db = MagicMock()
        svc = MetricsAggregationService(database=mock_db)
        assert svc._db is mock_db


class TestGetExecutionMetrics:
    @pytest.mark.asyncio
    async def test_returns_empty_metrics_when_no_rows(self) -> None:
        mock_db = _make_mock_db([("exec", [])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_execution_metrics()
        assert isinstance(result, ExecutionMetrics)
        assert result.total_executions == 0
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_computes_metrics_from_row(self) -> None:
        row = {
            "total_executions": 100,
            "successful": 80,
            "failed": 20,
            "avg_duration": 150.5,
            "min_duration": 10.0,
            "max_duration": 5000.0,
            "p50_duration": 120.0,
            "p95_duration": 3000.0,
            "p99_duration": 4500.0,
            "first_finished": datetime(2026, 6, 1, 0, 0, 0),
            "last_finished": datetime(2026, 6, 1, 1, 0, 0),
        }
        mock_db = _make_mock_db([("exec", [row])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_execution_metrics()
        assert result.total_executions == 100
        assert result.successful_executions == 80
        assert result.failed_executions == 20
        assert result.success_rate == 0.8
        assert result.avg_duration_ms == 150.5
        assert result.min_duration_ms == 10.0
        assert result.max_duration_ms == 5000.0
        assert result.p50_duration_ms == 120.0
        assert result.p95_duration_ms == 3000.0
        assert result.p99_duration_ms == 4500.0
        assert result.throughput_per_minute > 0

    @pytest.mark.asyncio
    async def test_handles_zero_span_seconds(self) -> None:
        same_time = datetime(2026, 6, 1, 12, 0, 0)
        row = {
            "total_executions": 5,
            "successful": 5,
            "failed": 0,
            "avg_duration": 50.0,
            "min_duration": 50.0,
            "max_duration": 50.0,
            "p50_duration": 50.0,
            "p95_duration": 50.0,
            "p99_duration": 50.0,
            "first_finished": same_time,
            "last_finished": same_time,
        }
        mock_db = _make_mock_db([("exec", [row])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_execution_metrics()
        assert result.throughput_per_minute == 5.0

    @pytest.mark.asyncio
    async def test_default_query_used_when_none(self) -> None:
        mock_db = _make_mock_db([("exec", [])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_execution_metrics(None)
        assert isinstance(result, ExecutionMetrics)

    @pytest.mark.asyncio
    async def test_custom_query_with_task_id(self) -> None:
        tid = uuid4()
        mock_db = _make_mock_db([("exec", [])])
        svc = MetricsAggregationService(database=mock_db)

        query = MetricsQuery(task_id=tid, time_range=TimeRange.LAST_WEEK)
        result = await svc.get_execution_metrics(query)
        assert isinstance(result, ExecutionMetrics)

    @pytest.mark.asyncio
    async def test_success_rate_calculation_edge_cases(self) -> None:
        row = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "p50_duration": 0,
            "p95_duration": 0,
            "p99_duration": 0,
            "first_finished": None,
            "last_finished": None,
        }
        mock_db = _make_mock_db([("exec", [row])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_execution_metrics()
        assert result.success_rate == 0.0
        assert result.throughput_per_minute == 0.0


class TestGetTaskMetrics:
    @pytest.mark.asyncio
    async def test_returns_none_when_task_not_found(self) -> None:
        mock_db = _make_mock_db([("task", [])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_task_metrics(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_task_metrics_when_found(self) -> None:
        tid = uuid4()
        task_row = {"id": tid, "name": "backup_task", "created_at": datetime(2026, 1, 1)}
        template_row = {"template_name": "backup_database"}
        time_row = {
            "first_exec": datetime(2026, 1, 2),
            "last_exec": datetime(2026, 6, 1),
        }
        exec_row = {
            "total_executions": 10,
            "successful": 9,
            "failed": 1,
            "avg_duration": 100.0,
            "min_duration": 50.0,
            "max_duration": 200.0,
            "p50_duration": 90.0,
            "p95_duration": 180.0,
            "p99_duration": 195.0,
            "first_finished": datetime(2026, 1, 2),
            "last_finished": datetime(2026, 6, 1),
        }
        mock_db = _make_mock_db([
            ("task", [task_row]),
            ("template", [template_row]),
            ("time", [time_row]),
            ("exec", [exec_row]),
        ])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_task_metrics(tid)
        assert result is not None
        assert result.task_id == tid
        assert result.task_name == "backup_task"
        assert result.template_name == "backup_database"
        assert result.execution.total_executions == 10

    @pytest.mark.asyncio
    async def test_handles_missing_template(self) -> None:
        tid = uuid4()
        task_row = {"id": tid, "name": "orphan_task", "created_at": datetime(2026, 1, 1)}
        time_row = {"first_exec": None, "last_exec": None}
        exec_row = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "p50_duration": 0,
            "p95_duration": 0,
            "p99_duration": 0,
            "first_finished": None,
            "last_finished": None,
        }
        mock_db = _make_mock_db([
            ("task", [task_row]),
            ("template", []),
            ("time", [time_row]),
            ("exec", [exec_row]),
        ])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_task_metrics(tid)
        assert result is not None
        assert result.template_name is None


class TestGetSystemMetrics:
    @pytest.mark.asyncio
    async def test_returns_system_metrics_with_empty_db(self) -> None:
        task_counts = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "running": 0,
            "cancelled": 0,
        }
        templates_row = {"cnt": 0}
        exec_row = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "p50_duration": 0,
            "p95_duration": 0,
            "p99_duration": 0,
            "first_finished": None,
            "last_finished": None,
        }
        mock_db = _make_mock_db([
            ("tasks", [task_counts]),
            ("templates", [templates_row]),
            ("exec", [exec_row]),
            ("top", []),
            ("fail", []),
        ])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_system_metrics()
        assert result.total_tasks == 0
        assert result.active_tasks == 0
        assert result.query_time_ms >= 0
        assert result.top_templates == []
        assert result.failure_patterns == []

    @pytest.mark.asyncio
    async def test_computes_active_tasks_correctly(self) -> None:
        task_counts = {
            "total": 100,
            "completed": 70,
            "failed": 10,
            "pending": 15,
            "running": 5,
            "cancelled": 0,
        }
        templates_row = {"cnt": 5}
        exec_row = {
            "total_executions": 500,
            "successful": 480,
            "failed": 20,
            "avg_duration": 100.0,
            "min_duration": 10.0,
            "max_duration": 1000.0,
            "p50_duration": 80.0,
            "p95_duration": 800.0,
            "p99_duration": 950.0,
            "first_finished": datetime(2026, 1, 1),
            "last_finished": datetime(2026, 6, 1),
        }
        top_templates = [
            {
                "template_name": "backup",
                "usage_count": 50,
                "success_count": 48,
                "failure_count": 2,
                "avg_confidence": 0.95,
                "success_rate": 0.96,
            }
        ]
        failure_patterns = [
            {
                "message": "Connection timeout",
                "occurrences": 10,
                "affected_tasks": 5,
                "last_occurred": datetime(2026, 6, 1),
            }
        ]
        mock_db = _make_mock_db([
            ("tasks", [task_counts]),
            ("templates", [templates_row]),
            ("exec", [exec_row]),
            ("top", top_templates),
            ("fail", failure_patterns),
        ])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_system_metrics()
        assert result.total_tasks == 100
        assert result.active_tasks == 20
        assert result.completed_tasks == 70
        assert result.failed_tasks == 10
        assert result.unique_templates_used == 5
        assert len(result.top_templates) == 1
        assert len(result.failure_patterns) == 1

    @pytest.mark.asyncio
    async def test_handles_none_task_counts(self) -> None:
        templates_row = {"cnt": None}
        exec_row = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "p50_duration": 0,
            "p95_duration": 0,
            "p99_duration": 0,
            "first_finished": None,
            "last_finished": None,
        }
        mock_db = _make_mock_db([
            ("tasks", [None]),
            ("templates", [templates_row]),
            ("exec", [exec_row]),
            ("top", []),
            ("fail", []),
        ])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_system_metrics()
        assert result.total_tasks == 0
        assert result.unique_templates_used == 0


class TestGetTopTemplates:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_data(self) -> None:
        mock_db = _make_mock_db([("top", [])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_top_templates(limit=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_templates_with_correct_structure(self) -> None:
        rows = [
            {
                "template_name": "backup_database",
                "usage_count": 100,
                "success_count": 95,
                "failure_count": 5,
                "avg_confidence": 0.95,
                "success_rate": 0.95,
            },
            {
                "template_name": "cleanup_files",
                "usage_count": 50,
                "success_count": 48,
                "failure_count": 2,
                "avg_confidence": 0.90,
                "success_rate": 0.96,
            },
        ]
        mock_db = _make_mock_db([("top", rows)])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_top_templates(limit=10)
        assert len(result) == 2
        assert result[0]["template_name"] == "backup_database"
        assert result[0]["usage_count"] == 100
        assert result[1]["template_name"] == "cleanup_files"


class TestGetFailurePatterns:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_failures(self) -> None:
        mock_db = _make_mock_db([("fail", [])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_failure_patterns(limit=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_patterns_with_correct_structure(self) -> None:
        last_occ = datetime(2026, 6, 3, 10, 30, 0)
        rows = [
            {
                "message": "Connection refused",
                "occurrences": 25,
                "affected_tasks": 8,
                "last_occurred": last_occ,
            },
            {
                "message": "Permission denied",
                "occurrences": 12,
                "affected_tasks": 4,
                "last_occurred": last_occ,
            },
        ]
        mock_db = _make_mock_db([("fail", rows)])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_failure_patterns(limit=10)
        assert len(result) == 2
        assert result[0]["message"] == "Connection refused"
        assert result[0]["occurrences"] == 25
        assert result[0]["affected_tasks"] == 8
        assert result[0]["last_occurred"] == last_occ


class TestGetActiveTaskCount:
    @pytest.mark.asyncio
    async def test_returns_zero_when_empty(self) -> None:
        mock_db = _make_mock_db([("count", [{"cnt": 0}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_active_task_count()
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_count_when_present(self) -> None:
        mock_db = _make_mock_db([("count", [{"cnt": 7}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_active_task_count()
        assert result == 7

    @pytest.mark.asyncio
    async def test_handles_none_row(self) -> None:
        mock_db = _make_mock_db([("count", [None])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_active_task_count()
        assert result == 0

    @pytest.mark.asyncio
    async def test_handles_none_cnt(self) -> None:
        mock_db = _make_mock_db([("count", [{"cnt": None}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_active_task_count()
        assert result == 0


class TestGetTasksByStatus:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty(self) -> None:
        mock_db = _make_mock_db([("status", [{"cnt": 0}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_tasks_by_status("RUNNING")
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_count_for_status(self) -> None:
        mock_db = _make_mock_db([("status", [{"cnt": 42}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_tasks_by_status("COMPLETED")
        assert result == 42

    @pytest.mark.asyncio
    async def test_handles_none_row(self) -> None:
        mock_db = _make_mock_db([("status", [None])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_tasks_by_status("FAILED")
        assert result == 0

    @pytest.mark.asyncio
    async def test_handles_none_cnt(self) -> None:
        mock_db = _make_mock_db([("status", [{"cnt": None}])])
        svc = MetricsAggregationService(database=mock_db)

        result = await svc.get_tasks_by_status("PENDING")
        assert result == 0
