from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from plasmaagent.observability.models import (
    ExecutionMetrics,
    MetricsQuery,
    SystemMetrics,
    TaskMetrics,
    TimeRange,
)


class TestTimeRange:
    def test_enum_values(self) -> None:
        assert TimeRange.LAST_HOUR == "last_hour"
        assert TimeRange.LAST_DAY == "last_day"
        assert TimeRange.LAST_WEEK == "last_week"
        assert TimeRange.LAST_MONTH == "last_month"
        assert TimeRange.ALL_TIME == "all_time"
        assert TimeRange.CUSTOM == "custom"

    def test_to_timedelta_last_hour(self) -> None:
        delta = TimeRange.LAST_HOUR.to_timedelta()
        assert delta == timedelta(hours=1)

    def test_to_timedelta_last_day(self) -> None:
        delta = TimeRange.LAST_DAY.to_timedelta()
        assert delta == timedelta(days=1)

    def test_to_timedelta_last_week(self) -> None:
        delta = TimeRange.LAST_WEEK.to_timedelta()
        assert delta == timedelta(weeks=1)

    def test_to_timedelta_last_month(self) -> None:
        delta = TimeRange.LAST_MONTH.to_timedelta()
        assert delta == timedelta(days=30)

    def test_to_timedelta_all_time_returns_none(self) -> None:
        assert TimeRange.ALL_TIME.to_timedelta() is None

    def test_to_timedelta_custom_returns_none(self) -> None:
        assert TimeRange.CUSTOM.to_timedelta() is None


class TestMetricsQuery:
    def test_default_values(self) -> None:
        q = MetricsQuery()
        assert q.time_range == TimeRange.LAST_DAY
        assert q.task_id is None
        assert q.template_name is None
        assert q.start_time is None
        assert q.end_time is None
        assert q.limit == 100

    def test_frozen_model(self) -> None:
        q = MetricsQuery()
        with pytest.raises(ValidationError):
            q.time_range = TimeRange.LAST_HOUR  # type: ignore[misc]

    def test_custom_time_range(self) -> None:
        q = MetricsQuery(time_range=TimeRange.LAST_WEEK)
        assert q.time_range == TimeRange.LAST_WEEK

    def test_with_task_id(self) -> None:
        tid = uuid4()
        q = MetricsQuery(task_id=tid)
        assert q.task_id == tid

    def test_with_template_name(self) -> None:
        q = MetricsQuery(template_name="backup_database")
        assert q.template_name == "backup_database"

    def test_template_name_max_length(self) -> None:
        q = MetricsQuery(template_name="x" * 200)
        assert len(q.template_name) == 200
        with pytest.raises(ValidationError):
            MetricsQuery(template_name="x" * 201)

    def test_limit_min_bound(self) -> None:
        q = MetricsQuery(limit=1)
        assert q.limit == 1
        with pytest.raises(ValidationError):
            MetricsQuery(limit=0)

    def test_limit_max_bound(self) -> None:
        q = MetricsQuery(limit=10000)
        assert q.limit == 10000
        with pytest.raises(ValidationError):
            MetricsQuery(limit=10001)

    def test_end_time_must_be_after_start_time(self) -> None:
        start = datetime(2026, 1, 1, 12, 0, 0)
        end = datetime(2026, 1, 1, 10, 0, 0)
        with pytest.raises(ValidationError, match="end_time must be after start_time"):
            MetricsQuery(
                time_range=TimeRange.CUSTOM,
                start_time=start,
                end_time=end,
            )

    def test_end_time_equal_to_start_time_rejected(self) -> None:
        t = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError):
            MetricsQuery(
                time_range=TimeRange.CUSTOM,
                start_time=t,
                end_time=t,
            )

    def test_valid_custom_time_range(self) -> None:
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 2, 0, 0, 0)
        q = MetricsQuery(
            time_range=TimeRange.CUSTOM,
            start_time=start,
            end_time=end,
        )
        assert q.start_time == start
        assert q.end_time == end

    def test_get_time_bounds_last_hour(self) -> None:
        q = MetricsQuery(time_range=TimeRange.LAST_HOUR)
        start, end = q.get_time_bounds()
        assert start is not None
        delta = end - start
        assert timedelta(minutes=59) <= delta <= timedelta(minutes=61)

    def test_get_time_bounds_last_day(self) -> None:
        q = MetricsQuery(time_range=TimeRange.LAST_DAY)
        start, end = q.get_time_bounds()
        assert start is not None
        delta = end - start
        assert timedelta(hours=23) <= delta <= timedelta(hours=25)

    def test_get_time_bounds_all_time(self) -> None:
        q = MetricsQuery(time_range=TimeRange.ALL_TIME)
        start, end = q.get_time_bounds()
        assert start is None
        assert isinstance(end, datetime)

    def test_get_time_bounds_custom_with_both(self) -> None:
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        q = MetricsQuery(
            time_range=TimeRange.CUSTOM,
            start_time=start,
            end_time=end,
        )
        s, e = q.get_time_bounds()
        assert s == start
        assert e == end

    def test_get_time_bounds_custom_no_end_uses_now(self) -> None:
        start = datetime(2026, 1, 1)
        q = MetricsQuery(
            time_range=TimeRange.CUSTOM,
            start_time=start,
        )
        s, e = q.get_time_bounds()
        assert s == start
        assert isinstance(e, datetime)
        assert (datetime.utcnow() - e).total_seconds() < 5


class TestExecutionMetrics:
    def test_default_values(self) -> None:
        m = ExecutionMetrics()
        assert m.total_executions == 0
        assert m.successful_executions == 0
        assert m.failed_executions == 0
        assert m.success_rate == 0.0
        assert m.avg_duration_ms == 0.0
        assert m.min_duration_ms == 0.0
        assert m.max_duration_ms == 0.0
        assert m.p50_duration_ms == 0.0
        assert m.p95_duration_ms == 0.0
        assert m.p99_duration_ms == 0.0
        assert m.throughput_per_minute == 0.0

    def test_frozen_model(self) -> None:
        m = ExecutionMetrics()
        with pytest.raises(ValidationError):
            m.total_executions = 5  # type: ignore[misc]

    def test_valid_full_metrics(self) -> None:
        m = ExecutionMetrics(
            total_executions=100,
            successful_executions=90,
            failed_executions=10,
            success_rate=0.9,
            avg_duration_ms=150.5,
            min_duration_ms=10.0,
            max_duration_ms=5000.0,
            p50_duration_ms=120.0,
            p95_duration_ms=3000.0,
            p99_duration_ms=4500.0,
            throughput_per_minute=5.5,
        )
        assert m.total_executions == 100
        assert m.success_rate == 0.9

    def test_failed_exceeds_total_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match="failed_executions cannot exceed total_executions",
        ):
            ExecutionMetrics(
                total_executions=10,
                failed_executions=11,
            )

    def test_successful_exceeds_total_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match="successful_executions cannot exceed total_executions",
        ):
            ExecutionMetrics(
                total_executions=10,
                successful_executions=11,
            )

    def test_negative_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(total_executions=-1)

    def test_negative_successful_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(successful_executions=-1)

    def test_negative_failed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(failed_executions=-1)

    def test_success_rate_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(success_rate=-0.1)

    def test_success_rate_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(success_rate=1.1)

    def test_success_rate_boundary_zero(self) -> None:
        m = ExecutionMetrics(success_rate=0.0)
        assert m.success_rate == 0.0

    def test_success_rate_boundary_one(self) -> None:
        m = ExecutionMetrics(success_rate=1.0)
        assert m.success_rate == 1.0

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(avg_duration_ms=-1.0)

    def test_negative_min_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(min_duration_ms=-0.1)

    def test_negative_throughput_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionMetrics(throughput_per_minute=-1.0)

    def test_zero_values_all_accepted(self) -> None:
        m = ExecutionMetrics(
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            success_rate=0.0,
            avg_duration_ms=0.0,
        )
        assert m.total_executions == 0


class TestTaskMetrics:
    def test_creation_with_required_fields(self) -> None:
        tid = uuid4()
        execution = ExecutionMetrics()
        m = TaskMetrics(
            task_id=tid,
            task_name="backup_task",
            execution=execution,
        )
        assert m.task_id == tid
        assert m.task_name == "backup_task"
        assert m.execution == execution
        assert m.template_name is None
        assert m.last_executed_at is None
        assert m.first_executed_at is None

    def test_frozen_model(self) -> None:
        m = TaskMetrics(
            task_id=uuid4(),
            task_name="test",
            execution=ExecutionMetrics(),
        )
        with pytest.raises(ValidationError):
            m.task_name = "new_name"  # type: ignore[misc]

    def test_with_template_name(self) -> None:
        m = TaskMetrics(
            task_id=uuid4(),
            task_name="test",
            template_name="backup_database",
            execution=ExecutionMetrics(),
        )
        assert m.template_name == "backup_database"

    def test_template_name_max_length(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetrics(
                task_id=uuid4(),
                task_name="test",
                template_name="x" * 201,
                execution=ExecutionMetrics(),
            )

    def test_task_name_max_length(self) -> None:
        m = TaskMetrics(
            task_id=uuid4(),
            task_name="x" * 500,
            execution=ExecutionMetrics(),
        )
        assert len(m.task_name) == 500
        with pytest.raises(ValidationError):
            TaskMetrics(
                task_id=uuid4(),
                task_name="x" * 501,
                execution=ExecutionMetrics(),
            )

    def test_with_timestamps(self) -> None:
        first = datetime(2026, 1, 1)
        last = datetime(2026, 6, 1)
        m = TaskMetrics(
            task_id=uuid4(),
            task_name="test",
            execution=ExecutionMetrics(),
            first_executed_at=first,
            last_executed_at=last,
        )
        assert m.first_executed_at == first
        assert m.last_executed_at == last

    def test_with_rich_execution(self) -> None:
        execution = ExecutionMetrics(
            total_executions=50,
            successful_executions=45,
            failed_executions=5,
            success_rate=0.9,
            avg_duration_ms=200.0,
        )
        m = TaskMetrics(
            task_id=uuid4(),
            task_name="deploy_task",
            execution=execution,
        )
        assert m.execution.total_executions == 50
        assert m.execution.success_rate == 0.9


class TestSystemMetrics:
    def test_default_values(self) -> None:
        m = SystemMetrics(overall_execution=ExecutionMetrics())
        assert m.total_tasks == 0
        assert m.active_tasks == 0
        assert m.completed_tasks == 0
        assert m.failed_tasks == 0
        assert m.pending_tasks == 0
        assert m.running_tasks == 0
        assert m.cancelled_tasks == 0
        assert m.unique_templates_used == 0
        assert m.top_templates == []
        assert m.failure_patterns == []
        assert m.query_time_ms == 0.0

    def test_frozen_model(self) -> None:
        m = SystemMetrics(overall_execution=ExecutionMetrics())
        with pytest.raises(ValidationError):
            m.total_tasks = 10  # type: ignore[misc]

    def test_active_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValidationError, match="active_tasks cannot exceed total_tasks"):
            SystemMetrics(
                total_tasks=5,
                active_tasks=6,
                overall_execution=ExecutionMetrics(),
            )

    def test_valid_full_metrics(self) -> None:
        m = SystemMetrics(
            total_tasks=100,
            active_tasks=10,
            completed_tasks=70,
            failed_tasks=15,
            pending_tasks=5,
            running_tasks=5,
            cancelled_tasks=5,
            overall_execution=ExecutionMetrics(
                total_executions=1000,
                success_rate=0.95,
            ),
            unique_templates_used=12,
            top_templates=[{"template_name": "backup", "usage_count": 50}],
            failure_patterns=[{"message": "timeout", "occurrences": 5}],
            query_time_ms=12.5,
        )
        assert m.total_tasks == 100
        assert m.active_tasks == 10
        assert m.overall_execution.success_rate == 0.95
        assert len(m.top_templates) == 1
        assert len(m.failure_patterns) == 1

    def test_negative_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SystemMetrics(
                total_tasks=-1,
                overall_execution=ExecutionMetrics(),
            )

    def test_negative_query_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SystemMetrics(
                overall_execution=ExecutionMetrics(),
                query_time_ms=-1.0,
            )

    def test_active_equal_to_total_accepted(self) -> None:
        m = SystemMetrics(
            total_tasks=5,
            active_tasks=5,
            overall_execution=ExecutionMetrics(),
        )
        assert m.active_tasks == 5

    def test_empty_top_templates(self) -> None:
        m = SystemMetrics(
            overall_execution=ExecutionMetrics(),
            top_templates=[],
        )
        assert m.top_templates == []

    def test_failure_patterns_structure(self) -> None:
        patterns = [
            {
                "message": "Connection refused",
                "occurrences": 15,
                "affected_tasks": 3,
                "last_occurred": datetime(2026, 6, 3),
            }
        ]
        m = SystemMetrics(
            overall_execution=ExecutionMetrics(),
            failure_patterns=patterns,
        )
        assert m.failure_patterns[0]["occurrences"] == 15

    def test_boundary_active_zero_total_zero(self) -> None:
        m = SystemMetrics(
            total_tasks=0,
            active_tasks=0,
            overall_execution=ExecutionMetrics(),
        )
        assert m.total_tasks == 0
        assert m.active_tasks == 0
