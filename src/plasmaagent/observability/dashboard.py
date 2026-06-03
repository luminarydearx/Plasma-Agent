from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from plasmaagent.observability.metrics_service import MetricsAggregationService
from plasmaagent.observability.models import MetricsQuery, TimeRange

if TYPE_CHECKING:
    from plasmaagent.core.database import Database


class TerminalDashboard:
    def __init__(
        self,
        db: Database,
        refresh_interval: float = 2.0,
        console: Console | None = None,
    ) -> None:
        self._db = db
        self._refresh_interval = max(0.5, min(60.0, refresh_interval))
        self._console = console or Console()
        self._service = MetricsAggregationService(db)
        self._running = False

    @property
    def refresh_interval(self) -> float:
        return self._refresh_interval

    async def run(self, max_iterations: int | None = None) -> None:
        self._running = True
        iteration = 0

        with Live(
            self._generate_layout(),
            console=self._console,
            refresh_per_second=1,
            screen=True,
        ) as live:
            while self._running:
                try:
                    layout = await self._generate_layout_async()
                    live.update(layout)
                except Exception as e:
                    error_text = Text(f"Error updating dashboard: {e}", style="red")
                    live.update(error_text)

                iteration += 1
                if max_iterations is not None and iteration >= max_iterations:
                    break

                await asyncio.sleep(self._refresh_interval)

    def stop(self) -> None:
        self._running = False

    def _generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["left"].split_column(
            Layout(name="system"),
            Layout(name="tasks"),
        )
        layout["right"].split_column(
            Layout(name="top_templates"),
            Layout(name="failures"),
        )
        return layout

    async def _generate_layout_async(self) -> Layout:
        layout = self._generate_layout()

        try:
            system_metrics = await self._service.get_system_metrics()
            execution_metrics = await self._service.get_execution_metrics(
                MetricsQuery(time_range=TimeRange.LAST_HOUR)
            )
            top_templates = await self._service.get_top_templates(limit=10)
            failure_patterns = await self._service.get_failure_patterns(limit=5)
        except Exception:
            system_metrics = None
            execution_metrics = None
            top_templates = []
            failure_patterns = []

        layout["header"].update(self._render_header())
        layout["system"].update(self._render_system_metrics(system_metrics))
        layout["tasks"].update(self._render_execution_metrics(execution_metrics))
        layout["top_templates"].update(self._render_top_templates(top_templates))
        layout["failures"].update(self._render_failures(failure_patterns))
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self) -> Panel:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        header_text = Text()
        header_text.append("🔥 PlasmaAgent Dashboard", style="bold cyan")
        header_text.append(f"  |  {now}", style="dim")
        return Panel(header_text, style="cyan", border_style="cyan")

    def _render_system_metrics(self, metrics: object | None) -> Panel:
        if metrics is None:
            return Panel(Text("Loading...", style="yellow"), title="📊 System Overview")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")

        table.add_row("Total Tasks", str(metrics.total_tasks))
        table.add_row("Active Tasks", str(metrics.active_tasks))
        table.add_row("Pending", str(metrics.pending_tasks))
        table.add_row("Running", str(metrics.running_tasks))
        table.add_row("Completed", str(metrics.completed_tasks))
        table.add_row("Failed", str(metrics.failed_tasks))
        table.add_row("Cancelled", str(metrics.cancelled_tasks))
        table.add_row("Unique Templates", str(metrics.unique_templates_used))

        return Panel(table, title="📊 System Overview", border_style="blue")

    def _render_execution_metrics(self, metrics: object | None) -> Panel:
        if metrics is None:
            return Panel(Text("Loading...", style="yellow"), title="⚡ Last Hour Performance")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green")

        success_rate = f"{metrics.success_rate * 100:.1f}%"
        table.add_row("Total Executions", str(metrics.total_executions))
        table.add_row("Successful", str(metrics.successful_executions))
        table.add_row("Failed", str(metrics.failed_executions))
        table.add_row("Success Rate", success_rate)

        if metrics.avg_execution_time_ms is not None:
            table.add_row("Avg Time", f"{metrics.avg_execution_time_ms:.0f}ms")
        if metrics.p50_execution_time_ms is not None:
            table.add_row("P50 Time", f"{metrics.p50_execution_time_ms:.0f}ms")
        if metrics.p95_execution_time_ms is not None:
            table.add_row("P95 Time", f"{metrics.p95_execution_time_ms:.0f}ms")
        if metrics.throughput_per_minute is not None:
            table.add_row("Throughput", f"{metrics.throughput_per_minute:.1f}/min")

        return Panel(table, title="⚡ Last Hour Performance", border_style="green")

    def _render_top_templates(self, templates: list[object]) -> Panel:
        if not templates:
            return Panel(Text("No data yet", style="dim"), title="🏆 Top Templates")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Template", style="cyan")
        table.add_column("Usage", justify="right", style="bold")
        table.add_column("Success", justify="right", style="green")

        for i, tmpl in enumerate(templates[:10], 1):
            template_name = getattr(tmpl, "template_name", "Unknown")
            usage_count = getattr(tmpl, "usage_count", 0)
            success_rate = getattr(tmpl, "success_rate", 0.0)

            table.add_row(
                str(i),
                template_name[:30],
                str(usage_count),
                f"{success_rate * 100:.0f}%",
            )

        return Panel(table, title="🏆 Top Templates", border_style="magenta")

    def _render_failures(self, failures: list[object]) -> Panel:
        if not failures:
            return Panel(Text("No failures! 🎉", style="green"), title="❌ Recent Failures")

        table = Table(show_header=True, header_style="bold red")
        table.add_column("Error", style="red")
        table.add_column("Count", justify="right", style="bold")

        for failure in failures[:5]:
            error_msg = getattr(failure, "error_message", "Unknown")
            count = getattr(failure, "count", 0)

            error_display = error_msg[:40] + "..." if len(error_msg) > 40 else error_msg
            table.add_row(error_display, str(count))

        return Panel(table, title="❌ Recent Failures", border_style="red")

    def _render_footer(self) -> Panel:
        footer_text = Text()
        footer_text.append(f"Auto-refresh: {self._refresh_interval}s", style="dim")
        footer_text.append("  |  ", style="dim")
        footer_text.append("Press Ctrl+C to exit", style="bold yellow")
        return Panel(footer_text, style="dim", border_style="dim")
