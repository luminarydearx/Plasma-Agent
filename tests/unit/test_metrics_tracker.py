from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from plasmaagent.ai.metrics.tracker import ExecutionMetricsTracker
from plasmaagent.core.database import Database, get_database


@pytest.fixture
async def db() -> Database:
    db = get_database()
    await db.connect()
    yield db
    await db.disconnect()


@pytest.fixture
async def tracker(db: Database) -> ExecutionMetricsTracker:
    return ExecutionMetricsTracker(db, retention_days=30)


@pytest.fixture
async def cleanup_telemetry(db: Database):
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")
    yield
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")


class TestExecutionMetricsTrackerInit:
    def test_init_default_retention(self, db: Database):
        tracker = ExecutionMetricsTracker(db)
        assert tracker._db == db
        assert tracker._retention_days == 30

    def test_init_custom_retention(self, db: Database):
        tracker = ExecutionMetricsTracker(db, retention_days=7)
        assert tracker._retention_days == 7


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerTracking:
    async def test_track_successful_execution(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1500,
            commands=["pg_dump", "gzip"],
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
        assert stats["failed_executions"] == 0
        assert stats["success_rate"] == 1.0

    async def test_track_failed_execution(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message="Connection refused",
            commands=["pg_dump"],
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 0
        assert stats["failed_executions"] == 1
        assert stats["success_rate"] == 0.0

    async def test_track_multiple_executions(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=2000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message="Timeout",
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 2
        assert stats["failed_executions"] == 1
        assert stats["success_rate"] == 0.67

    async def test_track_with_task_id(self, tracker: ExecutionMetricsTracker):
        task_id = uuid4()
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
            task_id=task_id,
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1

    async def test_track_with_metadata(self, tracker: ExecutionMetricsTracker):
        metadata = {"user": "admin", "environment": "production"}
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
            metadata=metadata,
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerStats:
    async def test_get_template_stats_empty(self, tracker: ExecutionMetricsTracker):
        stats = await tracker.get_template_stats("nonexistent_template")
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_execution_time_ms"] == 0

    async def test_get_template_stats_execution_times(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=2000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=3000,
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["avg_execution_time_ms"] == 2000
        assert stats["min_execution_time_ms"] == 1000
        assert stats["max_execution_time_ms"] == 3000

    async def test_get_all_template_stats(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )
        await tracker.track_execution(
            template_name="cleanup_files",
            success=True,
            execution_time_ms=500,
        )
        await tracker.track_execution(
            template_name="git_operations",
            success=False,
            execution_time_ms=2000,
            error_message="Git error",
        )

        all_stats = await tracker.get_all_template_stats()
        assert len(all_stats) == 3

        template_names = [s["template_name"] for s in all_stats]
        assert "backup_database" in template_names
        assert "cleanup_files" in template_names
        assert "git_operations" in template_names


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerFailures:
    async def test_get_failure_patterns_single_template(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message="Connection refused",
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=600,
            error_message="Connection refused",
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=700,
            error_message="Timeout",
        )

        patterns = await tracker.get_failure_patterns("backup_database")
        assert len(patterns) == 2

        connection_refused = next(
            (p for p in patterns if p["error_message"] == "Connection refused"), None
        )
        assert connection_refused is not None
        assert connection_refused["occurrence_count"] == 2

    async def test_get_failure_patterns_all_templates(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message="Connection refused",
        )
        await tracker.track_execution(
            template_name="cleanup_files",
            success=False,
            execution_time_ms=600,
            error_message="Permission denied",
        )

        patterns = await tracker.get_failure_patterns()
        assert len(patterns) == 2

    async def test_get_failure_patterns_empty(
        self, tracker: ExecutionMetricsTracker
    ):
        patterns = await tracker.get_failure_patterns()
        assert patterns == []

    async def test_get_failure_patterns_with_limit(
        self, tracker: ExecutionMetricsTracker
    ):
        for i in range(5):
            await tracker.track_execution(
                template_name="backup_database",
                success=False,
                execution_time_ms=500,
                error_message=f"Error {i}",
            )

        patterns = await tracker.get_failure_patterns(limit=3)
        assert len(patterns) == 3


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerSlow:
    async def test_get_slow_executions(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=6000,
        )
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=10000,
        )

        slow = await tracker.get_slow_executions(threshold_ms=5000)
        assert len(slow) == 2
        assert all(s["execution_time_ms"] > 5000 for s in slow)

    async def test_get_slow_executions_empty(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )

        slow = await tracker.get_slow_executions(threshold_ms=5000)
        assert slow == []

    async def test_get_slow_executions_with_limit(
        self, tracker: ExecutionMetricsTracker
    ):
        for i in range(10):
            await tracker.track_execution(
                template_name="backup_database",
                success=True,
                execution_time_ms=6000 + i * 1000,
            )

        slow = await tracker.get_slow_executions(threshold_ms=5000, limit=5)
        assert len(slow) == 5


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerCleanup:
    async def test_cleanup_old_metrics(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )

        async with tracker._db.transaction() as conn:
            await conn.execute(
                """
                UPDATE telemetry
                SET timestamp = NOW() - INTERVAL '31 days'
                WHERE event_type = 'execution_metric'
                """
            )

        deleted = await tracker.cleanup_old_metrics()
        assert deleted == 1

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 0

    async def test_cleanup_old_metrics_no_old_data(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )

        deleted = await tracker.cleanup_old_metrics()
        assert deleted == 0


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerTopTemplates:
    async def test_get_top_templates(self, tracker: ExecutionMetricsTracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="backup_database",
                success=True,
                execution_time_ms=1000,
            )
        for i in range(3):
            await tracker.track_execution(
                template_name="cleanup_files",
                success=True,
                execution_time_ms=500,
            )
        for i in range(1):
            await tracker.track_execution(
                template_name="git_operations",
                success=True,
                execution_time_ms=2000,
            )

        top = await tracker.get_top_templates(limit=2)
        assert len(top) == 2
        assert top[0]["template_name"] == "backup_database"
        assert top[0]["total_executions"] == 5
        assert top[1]["template_name"] == "cleanup_files"
        assert top[1]["total_executions"] == 3

    async def test_get_top_templates_empty(self, tracker: ExecutionMetricsTracker):
        top = await tracker.get_top_templates()
        assert top == []


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerLowSuccess:
    async def test_get_low_success_rate_templates(
        self, tracker: ExecutionMetricsTracker
    ):
        for i in range(2):
            await tracker.track_execution(
                template_name="backup_database",
                success=True,
                execution_time_ms=1000,
            )
        for i in range(8):
            await tracker.track_execution(
                template_name="backup_database",
                success=False,
                execution_time_ms=500,
                error_message="Error",
            )

        await tracker.track_execution(
            template_name="cleanup_files",
            success=True,
            execution_time_ms=500,
        )

        low_success = await tracker.get_low_success_rate_templates(threshold=0.5)
        assert len(low_success) == 1
        assert low_success[0]["template_name"] == "backup_database"
        assert low_success[0]["success_rate"] == 0.2

    async def test_get_low_success_rate_templates_empty(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
        )

        low_success = await tracker.get_low_success_rate_templates(threshold=0.5)
        assert low_success == []


@pytest.mark.usefixtures("cleanup_telemetry")
class TestExecutionMetricsTrackerEdgeCases:
    async def test_track_execution_empty_commands(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1000,
            commands=[],
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1

    async def test_track_execution_zero_time(self, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=0,
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 1
        assert stats["avg_execution_time_ms"] == 0

    async def test_get_template_stats_special_characters(
        self, tracker: ExecutionMetricsTracker
    ):
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message="Error: 'quotes' and \"double quotes\"",
        )

        patterns = await tracker.get_failure_patterns("backup_database")
        assert len(patterns) == 1
        assert "quotes" in patterns[0]["error_message"]

    async def test_concurrent_tracking(self, tracker: ExecutionMetricsTracker):
        import asyncio

        tasks = []
        for i in range(10):
            task = tracker.track_execution(
                template_name="backup_database",
                success=True,
                execution_time_ms=1000 + i * 100,
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 10
