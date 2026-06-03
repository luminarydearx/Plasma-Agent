from typing import Optional

import typer

from plasmaagent.cli.theme import console, style_error, style_info, style_success
from plasmaagent.core.asyncio_compat import run_async

monitor_app = typer.Typer(
    name="monitor",
    help="Monitoring and observability commands",
    no_args_is_help=True,
)


@monitor_app.command()
def dashboard(
    refresh: float = typer.Option(
        2.0,
        "--refresh",
        "-r",
        help="Refresh interval in seconds (min 0.5, max 60)",
        min=0.5,
        max=60.0,
    ),
) -> None:
    async def run_dashboard() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.dashboard import TerminalDashboard

        db = get_database()
        await db.connect()

        try:
            dash = TerminalDashboard(db, refresh_interval=refresh)
            await dash.run()
        except KeyboardInterrupt:
            console.print("\n[yellow]Dashboard stopped by user[/yellow]")
        finally:
            await db.disconnect()

    try:
        run_async(run_dashboard())
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped by user[/yellow]")


@monitor_app.command()
def metrics(
    hours: int = typer.Option(
        1,
        "--hours",
        "-h",
        help="Time range in hours (1-720)",
        min=1,
        max=720,
    ),
) -> None:
    async def show_metrics() -> None:
        from datetime import datetime, timedelta, timezone

        from plasmaagent.core.database import get_database
        from plasmaagent.observability.metrics_service import MetricsAggregationService
        from plasmaagent.observability.models import MetricsQuery, TimeRange

        db = get_database()
        await db.connect()

        try:
            service = MetricsAggregationService(db)
            query = MetricsQuery(time_range=TimeRange.CUSTOM)
            query.start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            query.end_time = datetime.now(timezone.utc)

            metrics = await service.get_execution_metrics(query)
            system = await service.get_system_metrics()

            console.print(f"\n[bold cyan]📊 Execution Metrics (Last {hours} hour(s))[/bold cyan]\n")
            console.print(f"  Total Executions:    [bold]{metrics.total_executions}[/bold]")
            console.print(f"  Successful:          [green]{metrics.successful_executions}[/green]")
            console.print(f"  Failed:              [red]{metrics.failed_executions}[/red]")
            console.print(f"  Success Rate:        [bold]{metrics.success_rate * 100:.1f}%[/bold]")

            if metrics.avg_execution_time_ms:
                console.print(f"  Avg Time:            {metrics.avg_execution_time_ms:.0f}ms")
            if metrics.p50_execution_time_ms:
                console.print(f"  P50 Time:            {metrics.p50_execution_time_ms:.0f}ms")
            if metrics.p95_execution_time_ms:
                console.print(f"  P95 Time:            {metrics.p95_execution_time_ms:.0f}ms")
            if metrics.throughput_per_minute:
                console.print(f"  Throughput:          {metrics.throughput_per_minute:.1f}/min")

            console.print(f"\n[bold cyan]📈 System Overview[/bold cyan]\n")
            console.print(f"  Total Tasks:         [bold]{system.total_tasks}[/bold]")
            console.print(f"  Active Tasks:        [yellow]{system.active_tasks}[/yellow]")
            console.print(f"  Completed:           [green]{system.completed_tasks}[/green]")
            console.print(f"  Failed:              [red]{system.failed_tasks}[/red]")
            console.print(f"  Unique Templates:    {system.unique_templates_used}")
            console.print()

        finally:
            await db.disconnect()

    run_async(show_metrics())


@monitor_app.command()
def top_templates(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of templates to show",
        min=1,
        max=100,
    ),
) -> None:
    async def show_top() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.metrics_service import MetricsAggregationService

        db = get_database()
        await db.connect()

        try:
            service = MetricsAggregationService(db)
            templates = await service.get_top_templates(limit=limit)

            if not templates:
                console.print("\n[yellow]No template data available yet[/yellow]\n")
                return

            console.print(f"\n[bold magenta]🏆 Top {limit} Templates[/bold magenta]\n")

            for i, tmpl in enumerate(templates, 1):
                name = tmpl.template_name if hasattr(tmpl, "template_name") else "Unknown"
                usage = tmpl.usage_count if hasattr(tmpl, "usage_count") else 0
                success = tmpl.success_rate if hasattr(tmpl, "success_rate") else 0.0

                console.print(f"  {i:2d}. {name[:40]:<40} Usage: [bold]{usage:>5}[/bold]  Success: [green]{success * 100:.0f}%[/green]")

            console.print()

        finally:
            await db.disconnect()

    run_async(show_top())


@monitor_app.command()
def failures(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of failure patterns to show",
        min=1,
        max=100,
    ),
) -> None:
    async def show_failures() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.metrics_service import MetricsAggregationService

        db = get_database()
        await db.connect()

        try:
            service = MetricsAggregationService(db)
            patterns = await service.get_failure_patterns(limit=limit)

            if not patterns:
                console.print("\n[green]🎉 No failures recorded![/green]\n")
                return

            console.print(f"\n[bold red]❌ Top {limit} Failure Patterns[/bold red]\n")

            for i, pattern in enumerate(patterns, 1):
                msg = pattern.error_message if hasattr(pattern, "error_message") else "Unknown"
                count = pattern.count if hasattr(pattern, "count") else 0

                msg_display = msg[:60] + "..." if len(msg) > 60 else msg
                console.print(f"  {i:2d}. [red]{msg_display}[/red]")
                console.print(f"      Occurrences: [bold]{count}[/bold]")

            console.print()

        finally:
            await db.disconnect()

    run_async(show_failures())
