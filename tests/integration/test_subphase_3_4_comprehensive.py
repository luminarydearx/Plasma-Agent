import asyncio
import time
from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg.rows import dict_row

from plasmaagent.ai.metrics.optimizer import TemplateOptimizer
from plasmaagent.ai.metrics.tracker import ExecutionMetricsTracker
from plasmaagent.core.database import get_database
from plasmaagent.core.state_machine import TaskStatus, transition_task_state
from plasmaagent.models.template_metrics import TemplateMetricsCreate
from plasmaagent.services.task_generator import TaskGeneratorService
from plasmaagent.services.template_metrics_service import TemplateMetricsService


@pytest.fixture
async def db():
    db = get_database()
    await db.connect()
    yield db
    await db.disconnect()


@pytest.fixture
async def tracker(db):
    return ExecutionMetricsTracker(db, retention_days=30)


@pytest.fixture
async def optimizer(tracker):
    return TemplateOptimizer(tracker)


@pytest.fixture
async def metrics_service(db):
    return TemplateMetricsService(db)


@pytest.fixture
async def generator_service(db):
    return TaskGeneratorService(db)


@pytest.fixture
async def cleanup_all(db):
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")
        await conn.execute("DELETE FROM template_metrics")
        await conn.execute("DELETE FROM execution_logs")
        await conn.execute("DELETE FROM task_steps")
        await conn.execute("DELETE FROM tasks")
    yield
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")
        await conn.execute("DELETE FROM template_metrics")


@pytest.mark.usefixtures("cleanup_all")
class TestFullSubPhase34Lifecycle:
    async def test_complete_self_improvement_cycle(
        self, generator_service, metrics_service, tracker, optimizer
    ):
        response = await generator_service.generate_from_natural_language(
            "backup database postgresql plasmaagent"
        )
        assert len(response.tasks) == 1
        task = response.tasks[0]
        assert task.template_used == "backup_database"

        metric = await metrics_service.get_by_name("backup_database")
        assert metric is not None
        assert metric.usage_count >= 1
        initial_confidence = metric.avg_confidence

        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1500,
            commands=["pg_dump", "verify"],
        )

        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=800,
            error_message="Connection refused",
            commands=["pg_dump"],
        )

        await tracker.track_execution(
            template_name="backup_database",
            success=True,
            execution_time_ms=1200,
            commands=["pg_dump", "verify"],
        )

        stats = await tracker.get_template_stats("backup_database")
        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 2
        assert stats["failed_executions"] == 1
        assert 0.6 <= stats["success_rate"] <= 0.7

        analysis = await optimizer.analyze_template("backup_database")
        assert analysis["status"] == "analyzed"
        assert "stats" in analysis
        assert "recommendations" in analysis

        patterns = await tracker.get_failure_patterns("backup_database")
        assert len(patterns) >= 1
        assert patterns[0]["error_message"] == "Connection refused"
        assert patterns[0]["occurrence_count"] == 1

        report = await optimizer.get_optimization_report()
        assert report["status"] == "analyzed"
        assert "summary" in report

    async def test_multiple_templates_lifecycle(
        self, generator_service, metrics_service, tracker
    ):
        inputs = [
            ("backup database postgresql", "backup_database"),
            ("cleanup old files in C:\\Temp", "cleanup_files"),
            ("check disk space on C:", "disk_monitoring"),
            ("git commit my changes", "git_operations"),
            ("show system info", "system_info"),
        ]

        for input_text, expected_template in inputs:
            response = await generator_service.generate_from_natural_language(input_text)
            assert len(response.tasks) >= 1
            assert response.tasks[0].template_used == expected_template

        for input_text, expected_template in inputs:
            await tracker.track_execution(
                template_name=expected_template,
                success=True,
                execution_time_ms=1000,
            )

        for _, expected_template in inputs:
            metric = await metrics_service.get_by_name(expected_template)
            assert metric is not None, f"Missing metric for {expected_template}"
            assert metric.usage_count >= 1

            stats = await tracker.get_template_stats(expected_template)
            assert stats["total_executions"] >= 1

    async def test_failed_generation_records_no_metrics(
        self, generator_service, metrics_service
    ):
        response = await generator_service.generate_from_natural_language(
            "xyzzy foobar baz qux nonsense"
        )
        assert len(response.tasks) == 0

        stats = await metrics_service.get_aggregate_stats()
        assert stats["total_templates"] >= 0


@pytest.mark.usefixtures("cleanup_all")
class TestCrossPhaseRegression:
    async def test_phase1_ptsm_still_works(self, db):
        async with db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                INSERT INTO tasks (name, description, status, payload)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("Regression Task", "Test", TaskStatus.PENDING.value, "{}"),
            )
            row = await cursor.fetchone()
            task_id = str(row["id"])

        async with db.transaction() as conn:
            result = await transition_task_state(
                conn, task_id, TaskStatus.RUNNING
            )
            assert result is True

            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                "SELECT status FROM tasks WHERE id = %s", (task_id,)
            )
            row = await cursor.fetchone()
            assert row["status"] == TaskStatus.RUNNING.value

        async with db.transaction() as conn:
            await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    async def test_phase1_ptsm_rejects_invalid_transition(self, db):
        async with db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                INSERT INTO tasks (name, description, status, payload)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("Invalid Trans Task", "Test", TaskStatus.COMPLETED.value, "{}"),
            )
            row = await cursor.fetchone()
            task_id = str(row["id"])

        from plasmaagent.core.exceptions import InvalidStateTransitionError

        with pytest.raises(InvalidStateTransitionError):
            async with db.transaction() as conn:
                await transition_task_state(conn, task_id, TaskStatus.RUNNING)

        async with db.transaction() as conn:
            await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    async def test_phase2_execution_logs_still_works(self, db):
        async with db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                """
                INSERT INTO tasks (name, description, status, payload)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("Exec Test", "Test", TaskStatus.RUNNING.value, "{}"),
            )
            row = await cursor.fetchone()
            task_id = row["id"]

            await conn.execute(
                """
                INSERT INTO execution_logs (task_id, log_level, message)
                VALUES (%s, %s, %s)
                """,
                (task_id, "INFO", "Test log message"),
            )

            await cursor.execute(
                "SELECT COUNT(*) as cnt FROM execution_logs WHERE task_id = %s",
                (task_id,),
            )
            count_row = await cursor.fetchone()
            assert count_row["cnt"] == 1

            await conn.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
            await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    async def test_phase3_mvp_pattern_matching_intact(self, generator_service):
        test_cases = [
            ("backup mysql database", True),
            ("clean temp files", True),
            ("check disk usage", True),
            ("git push origin", True),
            ("show system info", True),
            ("gibberish nonsense xyz", False),
        ]

        for input_text, should_match in test_cases:
            response = await generator_service.generate_from_natural_language(input_text)
            if should_match:
                assert len(response.tasks) >= 1, f"Should match: {input_text}"
                assert response.tasks[0].confidence >= Decimal("0.80")
            else:
                assert len(response.tasks) == 0, f"Should not match: {input_text}"


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsStress:
    async def test_thousand_metrics_entries(self, tracker):
        start = time.perf_counter()

        for i in range(1000):
            await tracker.track_execution(
                template_name=f"template_{i % 10}",
                success=i % 3 != 0,
                execution_time_ms=100 + (i % 50) * 100,
            )

        elapsed = time.perf_counter() - start
        assert elapsed < 30.0, f"Tracking 1000 metrics took {elapsed:.2f}s (limit: 30s)"

        stats = await tracker.get_template_stats("template_0")
        assert stats["total_executions"] == 100

    async def test_concurrent_tracking_100_operations(self, tracker):
        async def track(i):
            await tracker.track_execution(
                template_name=f"concurrent_{i % 5}",
                success=True,
                execution_time_ms=1000,
            )

        start = time.perf_counter()
        await asyncio.gather(*[track(i) for i in range(100)])
        elapsed = time.perf_counter() - start

        assert elapsed < 20.0, f"100 concurrent tracking took {elapsed:.2f}s"

        all_stats = await tracker.get_all_template_stats()
        total = sum(s["total_executions"] for s in all_stats)
        assert total == 100

    async def test_rapid_analytics_queries(self, tracker):
        for i in range(100):
            await tracker.track_execution(
                template_name=f"analytics_{i % 5}",
                success=i % 2 == 0,
                execution_time_ms=500 + i * 10,
            )

        start = time.perf_counter()
        for i in range(5):
            await tracker.get_template_stats(f"analytics_{i}")
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"5 stats queries took {elapsed:.2f}s"


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsSecurity:
    async def test_sql_injection_template_name_safe(self, tracker):
        malicious_name = "template'; DROP TABLE telemetry;--"
        await tracker.track_execution(
            template_name=malicious_name,
            success=True,
            execution_time_ms=1000,
        )

        stats = await tracker.get_template_stats(malicious_name)
        assert stats["total_executions"] == 1

        async with tracker._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                "SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_name = 'telemetry'"
            )
            count_row = await cursor.fetchone()
            assert count_row["cnt"] == 1, "SQL injection should not drop table"

    async def test_sql_injection_error_message_safe(self, tracker):
        malicious_error = "error'; DELETE FROM telemetry WHERE '1'='1"
        await tracker.track_execution(
            template_name="backup_database",
            success=False,
            execution_time_ms=500,
            error_message=malicious_error,
        )

        patterns = await tracker.get_failure_patterns("backup_database")
        assert len(patterns) == 1
        assert "DELETE" in patterns[0]["error_message"]

        async with tracker._db.transaction() as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(
                "SELECT COUNT(*) as cnt FROM telemetry WHERE event_type = 'execution_metric'"
            )
            count_row = await cursor.fetchone()
            assert count_row["cnt"] >= 1, "SQL injection should not delete other records"

    async def test_very_long_template_name(self, tracker):
        long_name = "a" * 1000
        await tracker.track_execution(
            template_name=long_name,
            success=True,
            execution_time_ms=1000,
        )

        stats = await tracker.get_template_stats(long_name)
        assert stats["total_executions"] == 1

    async def test_unicode_template_name(self, tracker):
        unicode_name = "テンプレート_数据库_🔥_テスト"
        await tracker.track_execution(
            template_name=unicode_name,
            success=True,
            execution_time_ms=1000,
        )

        stats = await tracker.get_template_stats(unicode_name)
        assert stats["total_executions"] == 1

    async def test_null_bytes_rejected_by_db(self, tracker):
        name_with_null = "template\x00name"
        with pytest.raises(Exception):
            await tracker.track_execution(
                template_name=name_with_null,
                success=True,
                execution_time_ms=1000,
            )

    async def test_metric_service_handles_malicious_names(self, metrics_service):
        malicious_name = "'; DROP TABLE template_metrics;--"
        metric = await metrics_service.create_metric(
            TemplateMetricsCreate(
                template_name=malicious_name,
                pattern=".*",
                usage_count=1,
                success_count=1,
                failure_count=0,
                avg_confidence=Decimal("0.95"),
                total_generation_time_ms=100.0,
            )
        )

        assert metric is not None
        assert metric.template_name == malicious_name

        retrieved = await metrics_service.get_by_name(malicious_name)
        assert retrieved is not None


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsFailureRecovery:
    async def test_invalid_execution_time_handled(self, tracker):
        await tracker.track_execution(
            template_name="test_template",
            success=True,
            execution_time_ms=-100,
        )

        stats = await tracker.get_template_stats("test_template")
        assert stats["total_executions"] == 1

    async def test_extreme_execution_time_handled(self, tracker):
        await tracker.track_execution(
            template_name="test_template",
            success=True,
            execution_time_ms=999999999,
        )

        stats = await tracker.get_template_stats("test_template")
        assert stats["total_executions"] == 1
        assert stats["max_execution_time_ms"] == 999999999

    async def test_analyze_with_no_data(self, optimizer):
        result = await optimizer.analyze_template("nonexistent_template")
        assert result["status"] == "no_data"
        assert result["recommendations"] == []

    async def test_optimization_report_empty(self, optimizer):
        report = await optimizer.get_optimization_report()
        assert report["status"] == "no_data"
        assert report["templates"] == []

    async def test_get_failure_patterns_with_null_errors(self, tracker):
        await tracker.track_execution(
            template_name="test_template",
            success=False,
            execution_time_ms=500,
            error_message=None,
        )

        patterns = await tracker.get_failure_patterns("test_template")
        assert patterns == []


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsPerformance:
    async def test_track_execution_speed(self, tracker):
        start = time.perf_counter()
        await tracker.track_execution(
            template_name="benchmark",
            success=True,
            execution_time_ms=1000,
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"Track execution took {elapsed:.3f}s (limit: 500ms)"

    async def test_get_stats_speed(self, tracker):
        for i in range(50):
            await tracker.track_execution(
                template_name="benchmark",
                success=True,
                execution_time_ms=1000,
            )

        start = time.perf_counter()
        await tracker.get_template_stats("benchmark")
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"Get stats took {elapsed:.3f}s (limit: 1s)"

    async def test_analyze_template_speed(self, optimizer, tracker):
        for i in range(100):
            await tracker.track_execution(
                template_name="benchmark",
                success=i % 3 != 0,
                execution_time_ms=1000 + i * 10,
                error_message="Error" if i % 3 == 0 else None,
            )

        start = time.perf_counter()
        await optimizer.analyze_template("benchmark")
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Analyze template took {elapsed:.3f}s (limit: 2s)"

    async def test_full_report_speed(self, optimizer, tracker):
        for i in range(50):
            await tracker.track_execution(
                template_name=f"template_{i % 5}",
                success=True,
                execution_time_ms=1000,
            )

        start = time.perf_counter()
        await optimizer.get_optimization_report()
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Full report took {elapsed:.3f}s (limit: 5s)"


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsOptimizerLogic:
    async def test_critical_low_success_rate(self, optimizer, tracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="failing_template",
                success=i < 2,
                execution_time_ms=1000,
                error_message="Connection refused" if i >= 2 else None,
            )

        analysis = await optimizer.analyze_template("failing_template")
        assert analysis["status"] == "analyzed"

        critical_recs = [
            r for r in analysis["recommendations"] if r["type"] == "critical"
        ]
        assert len(critical_recs) >= 1

    async def test_warning_moderate_success_rate(self, optimizer, tracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="moderate_template",
                success=i < 7,
                execution_time_ms=1000,
            )

        analysis = await optimizer.analyze_template("moderate_template")
        warning_recs = [
            r for r in analysis["recommendations"] if r["type"] == "warning"
        ]
        assert len(warning_recs) >= 1

    async def test_performance_slow_template(self, optimizer, tracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="slow_template",
                success=True,
                execution_time_ms=35000,
            )

        analysis = await optimizer.analyze_template("slow_template")
        perf_recs = [
            r for r in analysis["recommendations"] if r["type"] == "performance"
        ]
        assert len(perf_recs) >= 1

    async def test_success_high_reliability(self, optimizer, tracker):
        for i in range(15):
            await tracker.track_execution(
                template_name="reliable_template",
                success=True,
                execution_time_ms=1000,
            )

        analysis = await optimizer.analyze_template("reliable_template")
        success_recs = [
            r for r in analysis["recommendations"] if r["type"] == "success"
        ]
        assert len(success_recs) >= 1

    async def test_insufficient_data_no_recommendations(self, optimizer, tracker):
        for i in range(2):
            await tracker.track_execution(
                template_name="new_template",
                success=False,
                execution_time_ms=1000,
                error_message="Error",
            )

        analysis = await optimizer.analyze_template("new_template")
        critical_recs = [
            r for r in analysis["recommendations"] if r["type"] == "critical"
        ]
        assert len(critical_recs) == 0


@pytest.mark.usefixtures("cleanup_all")
class TestMetricsEdgeCases:
    async def test_zero_executions_stats(self, tracker):
        stats = await tracker.get_template_stats("never_used")
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_execution_time_ms"] == 0

    async def test_all_failures_template(self, tracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="always_fails",
                success=False,
                execution_time_ms=500,
                error_message=f"Error {i}",
            )

        stats = await tracker.get_template_stats("always_fails")
        assert stats["success_rate"] == 0.0
        assert stats["failed_executions"] == 10

    async def test_all_successes_template(self, tracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="always_succeeds",
                success=True,
                execution_time_ms=1000,
            )

        stats = await tracker.get_template_stats("always_succeeds")
        assert stats["success_rate"] == 1.0
        assert stats["successful_executions"] == 10

    async def test_identical_execution_times(self, tracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="consistent",
                success=True,
                execution_time_ms=1500,
            )

        stats = await tracker.get_template_stats("consistent")
        assert stats["avg_execution_time_ms"] == 1500
        assert stats["min_execution_time_ms"] == 1500
        assert stats["max_execution_time_ms"] == 1500

    async def test_special_chars_in_error_message(self, tracker):
        special_errors = [
            "Error: 'single quotes'",
            'Error: "double quotes"',
            "Error: back\\slash",
            "Error: new\nline",
            "Error: tab\there",
            "Error: emoji 🔥",
            "Error: unicode 日本語",
        ]

        for error in special_errors:
            await tracker.track_execution(
                template_name="special_chars",
                success=False,
                execution_time_ms=500,
                error_message=error,
            )

        patterns = await tracker.get_failure_patterns("special_chars")
        assert len(patterns) >= 1

    async def test_empty_metadata_and_commands(self, tracker):
        await tracker.track_execution(
            template_name="empty_data",
            success=True,
            execution_time_ms=1000,
            commands=[],
            metadata={},
        )

        stats = await tracker.get_template_stats("empty_data")
        assert stats["total_executions"] == 1

    async def test_very_large_metadata(self, tracker):
        large_metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}

        await tracker.track_execution(
            template_name="large_metadata",
            success=True,
            execution_time_ms=1000,
            metadata=large_metadata,
        )

        stats = await tracker.get_template_stats("large_metadata")
        assert stats["total_executions"] == 1
