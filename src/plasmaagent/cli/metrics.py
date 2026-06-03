from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import get_database
from plasmaagent.services.template_metrics_service import TemplateMetricsService

app = typer.Typer(help="Template metrics and analytics")
console = Console()


@app.command("stats")
def stats_command() -> None:
    async def _stats() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            stats = await service.get_aggregate_stats()

            console.print("\n[bold cyan]Template Metrics - Aggregate Statistics[/bold cyan]\n")
            console.print(f"  Total Templates: [green]{stats['total_templates']}[/green]")
            console.print(f"  Total Usage: [green]{stats['total_usage']}[/green]")
            console.print(f"  Total Success: [green]{stats['total_success']}[/green]")
            console.print(f"  Total Failure: [red]{stats['total_failure']}[/red]")

            success_rate = (
                (stats["total_success"] / stats["total_usage"] * 100)
                if stats["total_usage"] > 0
                else 0.0
            )
            console.print(f"  Success Rate: [cyan]{success_rate:.1f}%[/cyan]")
            console.print(f"  Avg Confidence: [cyan]{stats['global_avg_confidence']:.4f}[/cyan]")
            console.print(f"  Avg Generation Time: [cyan]{stats['avg_generation_time_ms']:.2f}ms[/cyan]")
            console.print()
        finally:
            await db.disconnect()

    run_async(_stats())


@app.command("top")
def top_command(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of templates to show"),
    by: str = typer.Option(
        "usage",
        "--by",
        "-b",
        help="Sort by: 'usage' or 'success'",
    ),
) -> None:
    async def _top() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            if by == "usage":
                metrics = await service.get_top_by_usage(limit=limit)
                title = "Top Templates by Usage"
            elif by == "success":
                metrics = await service.get_top_by_success_rate(limit=limit)
                title = "Top Templates by Success Rate"
            else:
                console.print(f"[red]Invalid sort option: {by}. Use 'usage' or 'success'[/red]")
                return

            table = Table(title=title)
            table.add_column("Template Name", style="cyan")
            table.add_column("Usage", justify="right", style="green")
            table.add_column("Success", justify="right", style="green")
            table.add_column("Failure", justify="right", style="red")
            table.add_column("Confidence", justify="right", style="magenta")
            table.add_column("Success Rate", justify="right", style="yellow")

            for metric in metrics:
                success_rate = (
                    (metric.success_count / metric.usage_count * 100)
                    if metric.usage_count > 0
                    else 0.0
                )
                table.add_row(
                    metric.template_name,
                    str(metric.usage_count),
                    str(metric.success_count),
                    str(metric.failure_count),
                    f"{metric.avg_confidence:.4f}",
                    f"{success_rate:.1f}%",
                )

            console.print()
            console.print(table)
            console.print()
        finally:
            await db.disconnect()

    run_async(_top())


@app.command("low")
def low_command(
    min_usage: int = typer.Option(5, "--min-usage", "-u", help="Minimum usage count"),
    max_rate: float = typer.Option(0.5, "--max-rate", "-r", help="Maximum success rate (0.0-1.0)"),
) -> None:
    async def _low() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            metrics = await service.get_low_performing(
                min_usage=min_usage,
                max_success_rate=max_rate,
            )

            table = Table(title="Low Performing Templates")
            table.add_column("Template Name", style="cyan")
            table.add_column("Pattern", style="dim")
            table.add_column("Usage", justify="right", style="yellow")
            table.add_column("Success", justify="right", style="green")
            table.add_column("Failure", justify="right", style="red")
            table.add_column("Success Rate", justify="right", style="red")

            for metric in metrics:
                success_rate = (
                    (metric.success_count / metric.usage_count * 100)
                    if metric.usage_count > 0
                    else 0.0
                )
                table.add_row(
                    metric.template_name,
                    metric.pattern[:50] + "..." if len(metric.pattern) > 50 else metric.pattern,
                    str(metric.usage_count),
                    str(metric.success_count),
                    str(metric.failure_count),
                    f"{success_rate:.1f}%",
                )

            console.print()
            if metrics:
                console.print(table)
            else:
                console.print("[green]No low-performing templates found[/green]")
            console.print()
        finally:
            await db.disconnect()

    run_async(_low())


@app.command("clear")
def clear_command(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    async def _clear() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            if not force:
                confirm = typer.confirm("This will delete ALL template metrics. Continue?")
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            all_metrics = await service.list_all(limit=10000)
            deleted_count = 0
            for metric in all_metrics:
                if await service.delete_metric(metric.id):
                    deleted_count += 1

            console.print(f"\n[green]Deleted {deleted_count} template metrics[/green]\n")
        finally:
            await db.disconnect()

    run_async(_clear())


@app.command("list")
def list_command(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of templates"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
) -> None:
    async def _list() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            metrics = await service.list_all(limit=limit, offset=offset)

            table = Table(title=f"Template Metrics (limit={limit}, offset={offset})")
            table.add_column("ID", style="dim")
            table.add_column("Template Name", style="cyan")
            table.add_column("Pattern", style="dim")
            table.add_column("Usage", justify="right", style="green")
            table.add_column("Success", justify="right", style="green")
            table.add_column("Confidence", justify="right", style="magenta")

            for metric in metrics:
                table.add_row(
                    str(metric.id)[:8],
                    metric.template_name,
                    metric.pattern[:30] + "..." if len(metric.pattern) > 30 else metric.pattern,
                    str(metric.usage_count),
                    str(metric.success_count),
                    f"{metric.avg_confidence:.4f}",
                )

            console.print()
            console.print(table)
            console.print(f"\n[dim]Showing {len(metrics)} of {limit} (offset={offset})[/dim]\n")
        finally:
            await db.disconnect()

    run_async(_list())
