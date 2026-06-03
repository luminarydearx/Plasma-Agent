from typing import Any

import pytest

from plasmaagent.ai.metrics.optimizer import TemplateOptimizer
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
async def optimizer(tracker: ExecutionMetricsTracker) -> TemplateOptimizer:
    return TemplateOptimizer(tracker)


@pytest.fixture
async def cleanup_telemetry(db: Database):
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")
    yield
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM telemetry WHERE event_type = 'execution_metric'")


@pytest.mark.usefixtures("cleanup_telemetry")
class TestTemplateOptimizerAnalyze:
    async def test_analyze_template_no_data(self, optimizer: TemplateOptimizer):
        result = await optimizer.analyze_template("nonexistent")
        assert result["status"] == "no_data"
        assert result["recommendations"] == []

    async def test_analyze_template_high_success(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="good_template",
                success=True,
                execution_time_ms=500,
            )

        result = await optimizer.analyze_template("good_template")
        assert result["status"] == "analyzed"
        assert result["stats"]["success_rate"] == 1.0
        
        success_recs = [r for r in result["recommendations"] if r["type"] == "success"]
        assert len(success_recs) > 0

    async def test_analyze_template_low_success(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(2):
            await tracker.track_execution(
                template_name="bad_template",
                success=True,
                execution_time_ms=500,
            )
        for i in range(8):
            await tracker.track_execution(
                template_name="bad_template",
                success=False,
                execution_time_ms=500,
                error_message="Command failed",
            )

        result = await optimizer.analyze_template("bad_template")
        assert result["status"] == "analyzed"
        assert result["stats"]["success_rate"] == 0.2
        
        critical_recs = [r for r in result["recommendations"] if r["type"] == "critical"]
        assert len(critical_recs) > 0

    async def test_analyze_template_with_failures(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="failing_template",
            success=False,
            execution_time_ms=500,
            error_message="Connection timeout",
        )
        await tracker.track_execution(
            template_name="failing_template",
            success=False,
            execution_time_ms=500,
            error_message="Connection timeout",
        )
        await tracker.track_execution(
            template_name="failing_template",
            success=False,
            execution_time_ms=500,
            error_message="Permission denied",
        )
        await tracker.track_execution(
            template_name="failing_template",
            success=True,
            execution_time_ms=500,
        )
        await tracker.track_execution(
            template_name="failing_template",
            success=True,
            execution_time_ms=500,
        )

        result = await optimizer.analyze_template("failing_template")
        assert result["status"] == "analyzed"
        assert len(result["top_failures"]) > 0
        
        error_pattern_recs = [r for r in result["recommendations"] if r["type"] == "error_pattern"]
        assert len(error_pattern_recs) > 0

    async def test_analyze_template_slow_execution(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="slow_template",
                success=True,
                execution_time_ms=35000,
            )

        result = await optimizer.analyze_template("slow_template")
        assert result["status"] == "analyzed"
        
        performance_recs = [r for r in result["recommendations"] if r["type"] == "performance"]
        assert len(performance_recs) > 0


@pytest.mark.usefixtures("cleanup_telemetry")
class TestTemplateOptimizerRecommendations:
    async def test_recommendation_critical_low_success(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="critical_template",
                success=True,
                execution_time_ms=500,
            )
        for i in range(20):
            await tracker.track_execution(
                template_name="critical_template",
                success=False,
                execution_time_ms=500,
                error_message="Fatal error",
            )

        result = await optimizer.analyze_template("critical_template")
        
        critical_recs = [r for r in result["recommendations"] if r["type"] == "critical"]
        assert len(critical_recs) > 0
        assert "Low success rate" in critical_recs[0]["issue"]

    async def test_recommendation_warning_moderate_success(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(7):
            await tracker.track_execution(
                template_name="warning_template",
                success=True,
                execution_time_ms=500,
            )
        for i in range(3):
            await tracker.track_execution(
                template_name="warning_template",
                success=False,
                execution_time_ms=500,
                error_message="Minor error",
            )

        result = await optimizer.analyze_template("warning_template")
        
        warning_recs = [r for r in result["recommendations"] if r["type"] == "warning"]
        assert len(warning_recs) > 0
        assert "Below-average" in warning_recs[0]["issue"]

    async def test_recommendation_performance_slow(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(5):
            await tracker.track_execution(
                template_name="slow_template",
                success=True,
                execution_time_ms=40000,
            )

        result = await optimizer.analyze_template("slow_template")
        
        performance_recs = [r for r in result["recommendations"] if r["type"] == "performance"]
        assert len(performance_recs) > 0
        assert "Slow execution" in performance_recs[0]["issue"]

    async def test_recommendation_success_high_reliability(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(20):
            await tracker.track_execution(
                template_name="excellent_template",
                success=True,
                execution_time_ms=500,
            )

        result = await optimizer.analyze_template("excellent_template")
        
        success_recs = [r for r in result["recommendations"] if r["type"] == "success"]
        assert len(success_recs) > 0
        assert "High reliability" in success_recs[0]["issue"]


@pytest.mark.usefixtures("cleanup_telemetry")
class TestTemplateOptimizerReport:
    async def test_optimization_report_no_data(self, optimizer: TemplateOptimizer):
        report = await optimizer.get_optimization_report()
        assert report["status"] == "no_data"
        assert report["templates"] == []

    async def test_optimization_report_mixed_templates(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(10):
            await tracker.track_execution(
                template_name="good_template",
                success=True,
                execution_time_ms=500,
            )

        for i in range(2):
            await tracker.track_execution(
                template_name="bad_template",
                success=True,
                execution_time_ms=500,
            )
        for i in range(8):
            await tracker.track_execution(
                template_name="bad_template",
                success=False,
                execution_time_ms=500,
                error_message="Error",
            )

        for i in range(5):
            await tracker.track_execution(
                template_name="slow_template",
                success=True,
                execution_time_ms=35000,
            )

        report = await optimizer.get_optimization_report()
        assert report["status"] == "analyzed"
        assert report["total_templates"] == 3
        assert len(report["problematic_templates"]) > 0
        assert len(report["well_performing_templates"]) > 0
        assert report["summary"]["needs_attention"] > 0
        assert report["summary"]["performing_well"] > 0

    async def test_optimization_report_insufficient_data(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        await tracker.track_execution(
            template_name="new_template",
            success=True,
            execution_time_ms=500,
        )
        await tracker.track_execution(
            template_name="new_template",
            success=False,
            execution_time_ms=500,
            error_message="Error",
        )

        report = await optimizer.get_optimization_report()
        assert report["status"] == "analyzed"
        assert report["total_templates"] == 1
        assert len(report["problematic_templates"]) == 0
        assert len(report["well_performing_templates"]) == 0


@pytest.mark.usefixtures("cleanup_telemetry")
class TestTemplateOptimizerEdgeCases:
    async def test_analyze_with_many_failures(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(50):
            await tracker.track_execution(
                template_name="failing_template",
                success=False,
                execution_time_ms=500,
                error_message=f"Error type {i % 5}",
            )

        result = await optimizer.analyze_template("failing_template")
        assert result["status"] == "analyzed"
        assert len(result["top_failures"]) <= 3

    async def test_analyze_with_zero_executions(self, optimizer: TemplateOptimizer):
        result = await optimizer.analyze_template("never_used")
        assert result["status"] == "no_data"
        assert result["recommendations"] == []

    async def test_report_with_all_good_templates(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(3):
            template_name = f"template_{i}"
            for j in range(10):
                await tracker.track_execution(
                    template_name=template_name,
                    success=True,
                    execution_time_ms=500,
                )

        report = await optimizer.get_optimization_report()
        assert report["status"] == "analyzed"
        assert len(report["well_performing_templates"]) == 3
        assert report["summary"]["performing_well"] == 3

    async def test_report_with_all_bad_templates(self, optimizer: TemplateOptimizer, tracker: ExecutionMetricsTracker):
        for i in range(3):
            template_name = f"bad_template_{i}"
            for j in range(2):
                await tracker.track_execution(
                    template_name=template_name,
                    success=True,
                    execution_time_ms=500,
                )
            for j in range(8):
                await tracker.track_execution(
                    template_name=template_name,
                    success=False,
                    execution_time_ms=500,
                    error_message="Error",
                )

        report = await optimizer.get_optimization_report()
        assert report["status"] == "analyzed"
        assert len(report["problematic_templates"]) == 3
        assert report["summary"]["needs_attention"] == 3
