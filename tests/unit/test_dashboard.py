import pytest
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch
from rich.console import Console

from plasmaagent.observability.dashboard import TerminalDashboard


def render_to_string(renderable: object) -> str:
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=200)
    console.print(renderable)
    return string_io.getvalue()


class TestTerminalDashboardInit:
    def test_init_default_refresh(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        assert dashboard.refresh_interval == 2.0

    def test_init_custom_refresh(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db, refresh_interval=5.0)
        assert dashboard.refresh_interval == 5.0

    def test_init_min_refresh(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db, refresh_interval=0.1)
        assert dashboard.refresh_interval == 0.5

    def test_init_max_refresh(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db, refresh_interval=120.0)
        assert dashboard.refresh_interval == 60.0

    def test_init_custom_console(self):
        db = MagicMock()
        console = Console()
        dashboard = TerminalDashboard(db, console=console)
        assert dashboard._console is console


class TestTerminalDashboardStop:
    def test_stop_sets_running_false(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        dashboard._running = True
        dashboard.stop()
        assert dashboard._running is False


class TestTerminalDashboardRender:
    def test_render_header(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_header()
        rendered = render_to_string(panel)
        assert "PlasmaAgent Dashboard" in rendered

    def test_render_system_metrics_none(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_system_metrics(None)
        rendered = render_to_string(panel)
        assert "Loading" in rendered

    def test_render_system_metrics_with_data(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        metrics = MagicMock()
        metrics.total_tasks = 100
        metrics.active_tasks = 5
        metrics.pending_tasks = 10
        metrics.running_tasks = 3
        metrics.completed_tasks = 80
        metrics.failed_tasks = 5
        metrics.cancelled_tasks = 2
        metrics.unique_templates_used = 15

        panel = dashboard._render_system_metrics(metrics)
        rendered = render_to_string(panel)
        assert "100" in rendered
        assert "System Overview" in rendered

    def test_render_execution_metrics_none(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_execution_metrics(None)
        rendered = render_to_string(panel)
        assert "Loading" in rendered

    def test_render_execution_metrics_with_data(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        metrics = MagicMock()
        metrics.total_executions = 50
        metrics.successful_executions = 45
        metrics.failed_executions = 5
        metrics.success_rate = 0.9
        metrics.avg_execution_time_ms = 150.0
        metrics.p50_execution_time_ms = 120.0
        metrics.p95_execution_time_ms = 300.0
        metrics.throughput_per_minute = 10.5

        panel = dashboard._render_execution_metrics(metrics)
        rendered = render_to_string(panel)
        assert "50" in rendered
        assert "90.0%" in rendered
        assert "Last Hour Performance" in rendered

    def test_render_top_templates_empty(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_top_templates([])
        rendered = render_to_string(panel)
        assert "No data" in rendered

    def test_render_top_templates_with_data(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        templates = []
        for i in range(3):
            tmpl = MagicMock()
            tmpl.template_name = f"template_{i}"
            tmpl.usage_count = 100 - i * 10
            tmpl.success_rate = 0.95 - i * 0.05
            templates.append(tmpl)

        panel = dashboard._render_top_templates(templates)
        rendered = render_to_string(panel)
        assert "template_0" in rendered
        assert "100" in rendered
        assert "Top Templates" in rendered

    def test_render_failures_empty(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_failures([])
        rendered = render_to_string(panel)
        assert "No failures" in rendered

    def test_render_failures_with_data(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        failures = []
        for i in range(2):
            failure = MagicMock()
            failure.error_message = f"Error {i}: Something went wrong"
            failure.count = 10 - i * 3
            failures.append(failure)

        panel = dashboard._render_failures(failures)
        rendered = render_to_string(panel)
        assert "Error 0" in rendered
        assert "Recent Failures" in rendered

    def test_render_footer(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        panel = dashboard._render_footer()
        rendered = render_to_string(panel)
        assert "Auto-refresh" in rendered
        assert "Ctrl+C" in rendered


class TestTerminalDashboardLayout:
    def test_generate_layout_structure(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        layout = dashboard._generate_layout()
        assert layout is not None
        assert layout.get("header") is not None
        assert layout.get("body") is not None
        assert layout.get("footer") is not None

    @pytest.mark.asyncio
    async def test_generate_layout_async_with_error(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)
        dashboard._service = MagicMock()
        dashboard._service.get_system_metrics = AsyncMock(side_effect=Exception("DB error"))
        dashboard._service.get_execution_metrics = AsyncMock(side_effect=Exception("DB error"))
        dashboard._service.get_top_templates = AsyncMock(side_effect=Exception("DB error"))
        dashboard._service.get_failure_patterns = AsyncMock(side_effect=Exception("DB error"))

        layout = await dashboard._generate_layout_async()
        assert layout is not None

    @pytest.mark.asyncio
    async def test_generate_layout_async_with_data(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db)

        system_metrics = MagicMock()
        system_metrics.total_tasks = 100
        system_metrics.active_tasks = 5
        system_metrics.pending_tasks = 10
        system_metrics.running_tasks = 3
        system_metrics.completed_tasks = 80
        system_metrics.failed_tasks = 5
        system_metrics.cancelled_tasks = 2
        system_metrics.unique_templates_used = 15

        execution_metrics = MagicMock()
        execution_metrics.total_executions = 50
        execution_metrics.successful_executions = 45
        execution_metrics.failed_executions = 5
        execution_metrics.success_rate = 0.9
        execution_metrics.avg_execution_time_ms = 150.0
        execution_metrics.p50_execution_time_ms = None
        execution_metrics.p95_execution_time_ms = None
        execution_metrics.throughput_per_minute = None

        dashboard._service = MagicMock()
        dashboard._service.get_system_metrics = AsyncMock(return_value=system_metrics)
        dashboard._service.get_execution_metrics = AsyncMock(return_value=execution_metrics)
        dashboard._service.get_top_templates = AsyncMock(return_value=[])
        dashboard._service.get_failure_patterns = AsyncMock(return_value=[])

        layout = await dashboard._generate_layout_async()
        assert layout is not None


class TestTerminalDashboardRun:
    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        db = MagicMock()
        dashboard = TerminalDashboard(db, refresh_interval=0.1)

        with patch.object(dashboard, "_generate_layout_async") as mock_gen:
            mock_layout = MagicMock()
            mock_gen.return_value = mock_layout

            with patch("plasmaagent.observability.dashboard.Live") as mock_live_class:
                mock_live = MagicMock()
                mock_live_class.return_value.__enter__ = MagicMock(return_value=mock_live)
                mock_live_class.return_value.__exit__ = MagicMock(return_value=False)

                await dashboard.run(max_iterations=3)

                assert mock_gen.call_count == 3
                assert mock_live.update.call_count == 3
