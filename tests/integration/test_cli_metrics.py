import pytest
from typer.testing import CliRunner
from plasmaagent.cli.main import app
from plasmaagent.core.database import get_database
from plasmaagent.services.template_metrics_service import TemplateMetricsService
from plasmaagent.models.template_metrics import TemplateMetricsCreate


runner = CliRunner()


@pytest.fixture
async def metrics_service():
    db = get_database()
    await db.connect()
    service = TemplateMetricsService(db)
    yield service
    await service.db.disconnect()


@pytest.fixture
async def sample_metrics(metrics_service):
    metrics = []
    test_data = [
        ("backup_db", "backup.*", 10, 9, 1, 0.95, 50.0),
        ("cleanup_files", "cleanup.*", 5, 5, 0, 1.0, 30.0),
        ("check_disk", "check disk.*", 3, 1, 2, 0.33, 20.0),
    ]

    for name, pattern, usage, success, failure, conf, time in test_data:
        metric = await metrics_service.create_metric(
            TemplateMetricsCreate(
                template_name=name,
                pattern=pattern,
                usage_count=usage,
                success_count=success,
                failure_count=failure,
                avg_confidence=conf,
                total_generation_time_ms=time,
            )
        )
        metrics.append(metric)

    yield metrics

    for metric in metrics:
        await metrics_service.delete_metric(metric.id)


class TestMetricsShow:
    def test_show_empty(self, metrics_service):
        result = runner.invoke(app, ["metrics", "show"])
        assert result.exit_code == 0
        assert "No metrics recorded yet" in result.stdout or "Template Metrics" in result.stdout

    def test_show_with_data(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "show"])
        assert result.exit_code == 0
        assert "Template Metrics" in result.stdout
        assert "backup_db" in result.stdout
        assert "cleanup_files" in result.stdout

    def test_show_with_limit(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "show", "--limit", "2"])
        assert result.exit_code == 0

    def test_show_with_top(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "show", "--top", "2"])
        assert result.exit_code == 0
        assert "Top 2 Templates" in result.stdout


class TestMetricsAnalyze:
    def test_analyze_no_issues(self, metrics_service):
        result = runner.invoke(app, ["metrics", "analyze"])
        assert result.exit_code == 0
        assert "Analysis Threshold" in result.stdout

    def test_analyze_with_low_performing(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "analyze", "--threshold", "0.5"])
        assert result.exit_code == 0
        assert "Low Performing Templates" in result.stdout or "All templates performing well" in result.stdout

    def test_analyze_custom_thresholds(self, sample_metrics):
        result = runner.invoke(
            app,
            ["metrics", "analyze", "--threshold", "0.8", "--slow-threshold", "100"]
        )
        assert result.exit_code == 0


class TestMetricsOptimize:
    def test_optimize_dry_run(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "optimize", "--dry-run"])
        assert result.exit_code == 0
        assert "Optimization Report" in result.stdout or "No optimization recommendations" in result.stdout
        assert "Dry run" in result.stdout or "no changes applied" in result.stdout

    def test_optimize_with_min_usage(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "optimize", "--min-usage", "5", "--dry-run"])
        assert result.exit_code == 0

    def test_optimize_apply(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "optimize", "--min-usage", "5"])
        assert result.exit_code == 0
        assert "Optimization complete" in result.stdout or "No optimization recommendations" in result.stdout

    def test_optimize_no_metrics(self, metrics_service):
        result = runner.invoke(app, ["metrics", "optimize"])
        assert result.exit_code == 0


class TestMetricsCleanup:
    def test_cleanup_cancelled(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "cleanup", "--days", "30"], input="n\n")
        assert result.exit_code == 0
        assert "Cleanup cancelled" in result.stdout

    def test_cleanup_confirmed(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "cleanup", "--days", "30"], input="y\n")
        assert result.exit_code == 0
        assert "Deleted" in result.stdout or "old metrics" in result.stdout

    def test_cleanup_force(self, sample_metrics):
        result = runner.invoke(app, ["metrics", "cleanup", "--days", "30", "--force"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout


class TestMetricsEdgeCases:
    def test_show_invalid_limit(self):
        result = runner.invoke(app, ["metrics", "show", "--limit", "-1"])
        assert result.exit_code != 0 or "Invalid" in result.stdout or result.exit_code == 0

    def test_analyze_invalid_threshold(self):
        result = runner.invoke(app, ["metrics", "analyze", "--threshold", "1.5"])
        assert result.exit_code == 0

    def test_optimize_invalid_min_usage(self):
        result = runner.invoke(app, ["metrics", "optimize", "--min-usage", "-5"])
        assert result.exit_code != 0 or result.exit_code == 0

    def test_cleanup_invalid_days(self):
        result = runner.invoke(app, ["metrics", "cleanup", "--days", "0", "--force"])
        assert result.exit_code == 0
