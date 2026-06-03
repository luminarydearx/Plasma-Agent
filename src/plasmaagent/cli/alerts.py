from typing import Optional
from uuid import UUID

import typer

from plasmaagent.cli.theme import console, style_error, style_info, style_success
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.observability.alert_models import (
    AlertCondition,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSeverity,
)

alerts_app = typer.Typer(
    name="alerts",
    help="Alert rules and notifications management",
    no_args_is_help=True,
)


@alerts_app.command(name="create")
def create_rule(
    name: str = typer.Option(..., "--name", "-n", help="Alert rule name"),
    metric: str = typer.Option(..., "--metric", "-m", help="Metric name to monitor"),
    condition: AlertCondition = typer.Option(..., "--condition", "-c", help="Condition type"),
    threshold: float = typer.Option(..., "--threshold", "-t", help="Threshold value"),
    webhook: str = typer.Option(..., "--webhook", "-w", help="Webhook URL"),
    severity: AlertSeverity = typer.Option(AlertSeverity.WARNING, "--severity", "-s", help="Alert severity"),
    description: str = typer.Option("", "--description", "-d", help="Rule description"),
    cooldown: int = typer.Option(300, "--cooldown", help="Cooldown in seconds"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing rule with same name"),
) -> None:
    async def create() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.alert_service import AlertService, DuplicateAlertRuleError

        db = get_database()
        await db.connect()

        try:
            service = AlertService(db)

            if force:
                await service.delete_rule_by_name(name)

            rule_data = AlertRuleCreate(
                name=name,
                description=description,
                metric_name=metric,
                condition=condition,
                threshold=threshold,
                severity=severity,
                webhook_url=webhook,
                cooldown_seconds=cooldown,
            )

            try:
                rule = await service.create_rule(rule_data)
            except DuplicateAlertRuleError:
                console.print(f"\n[red]Error: Alert rule '{name}' already exists.[/red]")
                console.print(f"[yellow]Use --force to overwrite or choose a different name.[/yellow]\n")
                raise typer.Exit(1)

            console.print(f"\n[bold green]✓ Alert rule created[/bold green]\n")
            console.print(f"  ID:        {rule.id}")
            console.print(f"  Name:      {rule.name}")
            console.print(f"  Metric:    {rule.metric_name}")
            console.print(f"  Condition: {rule.condition.value} {rule.threshold}")
            console.print(f"  Severity:  {rule.severity.value}")
            console.print(f"  Webhook:   {rule.webhook_url}")
            console.print()

        finally:
            await db.disconnect()

    run_async(create())


@alerts_app.command(name="list")
def list_rules(
    limit: int = typer.Option(50, "--limit", "-l", help="Number of rules to show"),
) -> None:
    async def list_all() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.alert_service import AlertService

        db = get_database()
        await db.connect()

        try:
            service = AlertService(db)
            rules = await service.list_rules(limit=limit)

            if not rules:
                console.print("\n[yellow]No alert rules found[/yellow]\n")
                return

            console.print(f"\n[bold cyan]Alert Rules ({len(rules)})[/bold cyan]\n")

            for rule in rules:
                status_icon = "✓" if rule.enabled else "✗"
                status_color = "green" if rule.enabled else "red"

                console.print(f"  [{status_color}]{status_icon}[/{status_color}] {rule.name}")
                console.print(f"    ID: {rule.id}")
                console.print(f"    Metric: {rule.metric_name} {rule.condition.value} {rule.threshold}")
                console.print(f"    Severity: {rule.severity.value} | Status: {rule.status.value}")
                console.print()

        finally:
            await db.disconnect()

    run_async(list_all())


@alerts_app.command(name="delete")
def delete_rule(
    rule_id: UUID = typer.Argument(..., help="Alert rule ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    async def delete() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.alert_service import AlertService

        db = get_database()
        await db.connect()

        try:
            service = AlertService(db)
            rule = await service.get_rule(rule_id)

            if rule is None:
                console.print(f"\n[red]Alert rule {rule_id} not found[/red]\n")
                raise typer.Exit(1)

            if not force:
                confirm = typer.confirm(f"Delete alert rule '{rule.name}'?")
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    raise typer.Exit(0)

            deleted = await service.delete_rule(rule_id)

            if deleted:
                console.print(f"\n[green]✓ Alert rule '{rule.name}' deleted[/green]\n")
            else:
                console.print(f"\n[red]Failed to delete alert rule[/red]\n")

        finally:
            await db.disconnect()

    run_async(delete())


@alerts_app.command(name="events")
def list_events(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of events to show"),
) -> None:
    async def list_all() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.alert_service import AlertService

        db = get_database()
        await db.connect()

        try:
            service = AlertService(db)
            events = await service.get_recent_events(limit=limit)

            if not events:
                console.print("\n[yellow]No alert events found[/yellow]\n")
                return

            console.print(f"\n[bold cyan]Recent Alert Events ({len(events)})[/bold cyan]\n")

            for event in events:
                severity_color = {"info": "blue", "warning": "yellow", "critical": "red"}.get(
                    event.severity.value, "white"
                )
                status_color = {"success": "green", "failed": "red", "error": "red"}.get(
                    event.webhook_status, "yellow"
                )

                console.print(f"  [{severity_color}]{event.severity.value.upper()}[/{severity_color}] {event.rule_name}")
                console.print(f"    {event.message}")
                console.print(f"    Webhook: [{status_color}]{event.webhook_status}[/{status_color}]")
                console.print(f"    Time: {event.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
                console.print()

        finally:
            await db.disconnect()

    run_async(list_all())


@alerts_app.command(name="test")
def test_alert(
    metric: str = typer.Option(..., "--metric", "-m", help="Metric name"),
    value: float = typer.Option(..., "--value", "-v", help="Metric value"),
) -> None:
    async def test() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.observability.alert_service import AlertService

        db = get_database()
        await db.connect()

        try:
            service = AlertService(db)
            events = await service.check_and_trigger(metric, value)

            if not events:
                console.print(f"\n[yellow]No alerts triggered for {metric}={value}[/yellow]\n")
                return

            console.print(f"\n[bold green]✓ {len(events)} alert(s) triggered[/bold green]\n")

            for event in events:
                console.print(f"  Rule: {event.rule_name}")
                console.print(f"  Severity: {event.severity.value}")
                console.print(f"  Message: {event.message}")
                console.print(f"  Webhook: {event.webhook_status}")
                console.print()

        finally:
            await db.disconnect()

    run_async(test())
