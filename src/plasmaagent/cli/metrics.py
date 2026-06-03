import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import Optional
from decimal import Decimal
from plasmaagent.services.template_metrics_service import TemplateMetricsService
from plasmaagent.cli.theme import pc
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import get_database

app = typer.Typer(help="Metrics management commands")
console = Console()


@app.command()
def show(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of metrics to display"),
    top: Optional[int] = typer.Option(None, "--top", "-t", help="Show only top N by usage")
) -> None:
    """Display template metrics and statistics."""
    async def _show() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            metrics = await service.list_all(limit=limit)

            if not metrics:
                console.print(Panel(
                    Text("No metrics recorded yet", style=f"bold {pc('plasma_magenta')}"),
                    border_style=pc('plasma_magenta')
                ))
                return

            table = Table(
                title="Template Metrics",
                border_style=pc('plasma_cyan'),
                header_style=f"bold {pc('solar_gold')}",
                show_lines=True
            )

            table.add_column("Template", style=pc('plasma_cyan'), no_wrap=True)
            table.add_column("Pattern", style=pc('plasma_violet'))
            table.add_column("Usage", justify="right", style=pc('aurora_green'))
            table.add_column("Success", justify="right", style=pc('aurora_green'))
            table.add_column("Failure", justify="right", style=pc('plasma_magenta'))
            table.add_column("Rate", justify="right", style=pc('solar_gold'))
            table.add_column("Confidence", justify="right", style=pc('plasma_violet'))
            table.add_column("Avg Time", justify="right", style=pc('cosmic_blue'))

            for metric in metrics:
                total = metric.success_count + metric.failure_count
                rate = (metric.success_count / total * 100) if total > 0 else 0
                confidence_pct = float(metric.avg_confidence) * 100
                avg_time = (metric.total_generation_time_ms / metric.usage_count) if metric.usage_count > 0 else 0

                table.add_row(
                    metric.template_name,
                    metric.pattern[:30] + "..." if len(metric.pattern) > 30 else metric.pattern,
                    str(metric.usage_count),
                    str(metric.success_count),
                    str(metric.failure_count),
                    f"{rate:.1f}%",
                    f"{confidence_pct:.0f}%",
                    f"{avg_time:.1f}ms"
                )

            console.print(table)

            stats = await service.get_aggregate_stats()
            total_exec = stats['total_success'] + stats['total_failure']
            success_rate = (stats['total_success'] / total_exec * 100) if total_exec > 0 else 0

            stats_panel = Panel(
                f"[{pc('plasma_cyan')}]Total Templates:[/{pc('plasma_cyan')}] {stats['total_templates']}\n"
                f"[{pc('aurora_green')}]Total Usage:[/{pc('aurora_green')}] {stats['total_usage']}\n"
                f"[{pc('aurora_green')}]Total Success:[/{pc('aurora_green')}] {stats['total_success']}\n"
                f"[{pc('plasma_magenta')}]Total Failure:[/{pc('plasma_magenta')}] {stats['total_failure']}\n"
                f"[{pc('solar_gold')}]Overall Success Rate:[/{pc('solar_gold')}] {success_rate:.1f}%",
                title="Aggregate Statistics",
                border_style=pc('plasma_violet')
            )
            console.print(stats_panel)

            if top:
                top_metrics = await service.get_top_by_usage(limit=top)

                if top_metrics:
                    table = Table(
                        title=f"Top {top} Templates by Usage",
                        border_style=pc('solar_gold'),
                        header_style=f"bold {pc('solar_gold')}"
                    )

                    table.add_column("#", style=pc('plasma_magenta'), justify="right")
                    table.add_column("Template", style=pc('plasma_cyan'))
                    table.add_column("Usage", justify="right", style=pc('aurora_green'))
                    table.add_column("Success Rate", justify="right", style=pc('aurora_green'))

                    for idx, metric in enumerate(top_metrics, 1):
                        total = metric.success_count + metric.failure_count
                        rate = (metric.success_count / total * 100) if total > 0 else 0
                        table.add_row(
                            str(idx),
                            metric.template_name,
                            str(metric.usage_count),
                            f"{rate:.1f}%"
                        )

                    console.print(table)
        finally:
            await db.disconnect()

    run_async(_show())


@app.command()
def analyze(
    max_success_rate: float = typer.Option(0.5, "--max-success-rate", "-m", help="Max success rate threshold"),
    min_usage: int = typer.Option(5, "--min-usage", "-u", help="Minimum usage count")
) -> None:
    """Analyze template performance and identify issues."""
    async def _analyze() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            low_performing = await service.get_low_performing(
                min_usage=min_usage,
                max_success_rate=max_success_rate
            )

            console.print(Panel(
                Text(
                    f"Analysis: templates with < {max_success_rate * 100:.0f}% success rate "
                    f"and >= {min_usage} usages",
                    style=f"bold {pc('plasma_cyan')}"
                ),
                border_style=pc('plasma_cyan')
            ))

            if low_performing:
                table = Table(
                    title="Low Performing Templates",
                    border_style=pc('plasma_magenta'),
                    header_style=f"bold {pc('plasma_magenta')}"
                )

                table.add_column("Template", style=pc('plasma_cyan'))
                table.add_column("Success Rate", justify="right", style=pc('plasma_magenta'))
                table.add_column("Failures", justify="right", style=pc('plasma_magenta'))
                table.add_column("Usage", justify="right", style=pc('plasma_violet'))

                for metric in low_performing:
                    total = metric.success_count + metric.failure_count
                    rate = (metric.success_count / total * 100) if total > 0 else 0
                    table.add_row(
                        metric.template_name,
                        f"{rate:.1f}%",
                        str(metric.failure_count),
                        str(metric.usage_count)
                    )

                console.print(table)
            else:
                console.print(Panel(
                    Text("All templates performing well!", style=f"bold {pc('aurora_green')}"),
                    border_style=pc('aurora_green')
                ))
        finally:
            await db.disconnect()

    run_async(_analyze())


@app.command()
def optimize(
    min_usage: int = typer.Option(5, "--min-usage", "-m", help="Minimum usage count for optimization"),
    min_success_rate: float = typer.Option(0.8, "--min-success-rate", "-s", help="Min success rate for high confidence"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show recommendations without applying")
) -> None:
    """Optimize template confidence scores based on performance."""
    async def _optimize() -> None:
        db = get_database()
        await db.connect()
        service = TemplateMetricsService(db)

        try:
            all_metrics = await service.list_all(limit=1000)

            if not all_metrics:
                console.print(Panel(
                    Text("No metrics available for optimization", style=f"bold {pc('plasma_magenta')}"),
                    border_style=pc('plasma_magenta')
                ))
                return

            recommendations = []
            for metric in all_metrics:
                if metric.usage_count >= min_usage:
                    total = metric.success_count + metric.failure_count
                    success_rate = metric.success_count / total if total > 0 else 0

                    if success_rate >= min_success_rate and float(metric.avg_confidence) < success_rate:
                        recommendations.append({
                            'metric': metric,
                            'current_confidence': float(metric.avg_confidence),
                            'recommended_confidence': success_rate,
                            'reason': f"High success rate ({success_rate * 100:.1f}%) but low confidence"
                        })

            if not recommendations:
                console.print(Panel(
                    Text("No optimization recommendations", style=f"bold {pc('aurora_green')}"),
                    border_style=pc('aurora_green')
                ))
                return

            table = Table(
                title="Optimization Recommendations",
                border_style=pc('solar_gold'),
                header_style=f"bold {pc('solar_gold')}"
            )

            table.add_column("Template", style=pc('plasma_cyan'))
            table.add_column("Current", justify="right", style=pc('plasma_magenta'))
            table.add_column("Recommended", justify="right", style=pc('aurora_green'))
            table.add_column("Reason", style=pc('plasma_violet'))

            for rec in recommendations:
                table.add_row(
                    rec['metric'].template_name,
                    f"{rec['current_confidence'] * 100:.0f}%",
                    f"{rec['recommended_confidence'] * 100:.0f}%",
                    rec['reason']
                )

            console.print(table)

            if not dry_run:
                console.print(Panel(
                    Text("Applying optimizations...", style=f"bold {pc('aurora_green')}"),
                    border_style=pc('aurora_green')
                ))

                for rec in recommendations:
                    metric = rec['metric']
                    new_confidence = Decimal(str(rec['recommended_confidence']))
                    await service.update_metric(
                        metric.id,
                        avg_confidence=new_confidence
                    )
                    console.print(
                        f"[{pc('aurora_green')}]✓[/{pc('aurora_green')}] {metric.template_name}: "
                        f"{rec['current_confidence']:.2f} → {rec['recommended_confidence']:.2f}"
                    )

                console.print(Panel(
                    Text("Optimization complete!", style=f"bold {pc('aurora_green')}"),
                    border_style=pc('aurora_green')
                ))
            else:
                console.print(Panel(
                    Text("Dry run - no changes applied", style=f"bold {pc('solar_gold')}"),
                    border_style=pc('solar_gold')
                ))
        finally:
            await db.disconnect()

    run_async(_optimize())
