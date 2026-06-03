from datetime import datetime
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import get_database
from plasmaagent.scheduling.service import SchedulingService
from plasmaagent.scheduling.onetime import OneTimeScheduler
from plasmaagent.scheduling.patterns import RecurringPatterns, RecurringPattern
from plasmaagent.scheduling.dependencies import DependencyType, TaskDependencyCreate
from plasmaagent.scheduling.dependency_service import DependencyService

app = typer.Typer(help="Manage scheduled tasks")
console = Console()


@app.command("create")
def create_schedule(
    task_id: str = typer.Argument(..., help="Task ID to schedule"),
    cron: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g., '0 9 * * *')"),
    pattern: RecurringPattern = typer.Option(None, "--pattern", "-p", help="Recurring pattern"),
    at: str = typer.Option(None, "--at", help="One-time schedule (ISO format datetime)"),
    in_seconds: int = typer.Option(None, "--in", help="One-time schedule (seconds from now)"),
    timezone: str = typer.Option(None, "--timezone", "-tz", help="Timezone (e.g., 'Asia/Jakarta')"),
) -> None:
    async def _create():
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            console.print(f"[red]✗ Invalid task ID format: {task_id}[/red]")
            raise typer.Exit(1)

        db = get_database()
        await db.connect()
        try:
            if cron:
                service = SchedulingService(db)
                result = await service.enable_schedule(
                    task_id=task_id_uuid,
                    cron_expression=cron,
                    timezone=timezone,
                )
            elif pattern:
                pattern_map = {
                    RecurringPattern.HOURLY: RecurringPatterns.hourly(),
                    RecurringPattern.DAILY: RecurringPatterns.daily(),
                    RecurringPattern.WEEKLY: RecurringPatterns.weekly(),
                    RecurringPattern.MONTHLY: RecurringPatterns.monthly(),
                    RecurringPattern.YEARLY: RecurringPatterns.yearly(),
                    RecurringPattern.WEEKDAYS: RecurringPatterns.weekdays(),
                    RecurringPattern.WEEKENDS: RecurringPatterns.weekends(),
                }
                cron_expr = pattern_map.get(pattern, RecurringPatterns.daily())
                service = SchedulingService(db)
                result = await service.enable_schedule(
                    task_id=task_id_uuid,
                    cron_expression=cron_expr,
                    timezone=timezone,
                )
            elif at:
                run_at = datetime.fromisoformat(at)
                scheduler = OneTimeScheduler(db)
                result = await scheduler.schedule_at(
                    task_id=task_id_uuid,
                    run_at=run_at,
                    timezone=timezone,
                )
            elif in_seconds is not None:
                scheduler = OneTimeScheduler(db)
                result = await scheduler.schedule_in(
                    task_id=task_id_uuid,
                    seconds=in_seconds,
                    timezone=timezone,
                )
            else:
                console.print("[red]Error: Must specify --cron, --pattern, --at, or --in[/red]")
                raise typer.Exit(1)

            if result:
                console.print(f"[green]✓ Scheduled task {task_id}[/green]")
                console.print(f"  Cron: {result.cron_expression or 'One-time'}")
                console.print(f"  Next run: {result.next_run_at}")
            else:
                console.print(f"[red]✗ Failed to schedule task {task_id}[/red]")
                raise typer.Exit(1)

        finally:
            await db.disconnect()

    run_async(_create())


@app.command("list")
def list_schedules(
    active_only: bool = typer.Option(False, "--active", "-a", help="Show only active schedules"),
) -> None:
    async def _list():
        db = get_database()
        await db.connect()
        try:
            service = SchedulingService(db)

            if active_only:
                tasks = await service.list_scheduled_tasks(is_scheduled=True, limit=100, offset=0)
            else:
                tasks = await service.list_scheduled_tasks(limit=100, offset=0)

            if not tasks:
                console.print("[yellow]No scheduled tasks found[/yellow]")
                return

            table = Table(title="Scheduled Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Cron", style="magenta")
            table.add_column("Next Run", style="yellow")
            table.add_column("Status", style="blue")

            for task in tasks:
                table.add_row(
                    str(task.id),
                    task.name,
                    task.cron_expression or "One-time",
                    str(task.next_run_at) if task.next_run_at else "N/A",
                    "Active" if task.is_scheduled else "Inactive",
                )

            console.print(table)
        finally:
            await db.disconnect()

    run_async(_list())


@app.command("delete")
def delete_schedule(
    task_id: str = typer.Argument(..., help="Task ID to unschedule"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    async def _delete():
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            console.print(f"[red]✗ Invalid task ID format: {task_id}[/red]")
            raise typer.Exit(1)

        if not force:
            confirm = typer.confirm(f"Delete schedule for task {task_id}?")
            if not confirm:
                raise typer.Abort()

        db = get_database()
        await db.connect()
        try:
            service = SchedulingService(db)
            result = await service.disable_schedule(task_id_uuid)

            if result:
                console.print(f"[green]✓ Deleted schedule for task {task_id}[/green]")
            else:
                console.print(f"[red]✗ Task {task_id} not found[/red]")
                raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_delete())


@app.command("enable")
def enable_schedule(
    task_id: str = typer.Argument(..., help="Task ID to enable"),
) -> None:
    async def _enable():
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            console.print(f"[red]✗ Invalid task ID format: {task_id}[/red]")
            raise typer.Exit(1)

        db = get_database()
        await db.connect()
        try:
            service = SchedulingService(db)
            task = await service.get_task(task_id_uuid)

            if not task or not task.cron_expression:
                console.print(f"[red]✗ Task {task_id} has no schedule configured[/red]")
                raise typer.Exit(1)

            result = await service.enable_schedule(
                task_id=task_id_uuid,
                cron_expression=task.cron_expression,
            )

            if result:
                console.print(f"[green]✓ Enabled schedule for task {task_id}[/green]")
            else:
                console.print(f"[red]✗ Failed to enable schedule[/red]")
                raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_enable())


@app.command("disable")
def disable_schedule(
    task_id: str = typer.Argument(..., help="Task ID to disable"),
) -> None:
    async def _disable():
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            console.print(f"[red]✗ Invalid task ID format: {task_id}[/red]")
            raise typer.Exit(1)

        db = get_database()
        await db.connect()
        try:
            service = SchedulingService(db)
            result = await service.disable_schedule(task_id_uuid)

            if result:
                console.print(f"[green]✓ Disabled schedule for task {task_id}[/green]")
            else:
                console.print(f"[red]✗ Task {task_id} not found[/red]")
                raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_disable())


@app.command("depends")
def add_dependency(
    source_id: str = typer.Argument(..., help="Source task ID (triggers target)"),
    target_id: str = typer.Argument(..., help="Target task ID (depends on source)"),
    on: DependencyType = typer.Option(
        DependencyType.ON_SUCCESS,
        "--on",
        help="Trigger condition",
    ),
) -> None:
    async def _add():
        try:
            source_uuid = UUID(source_id)
            target_uuid = UUID(target_id)
        except ValueError as e:
            console.print(f"[red]✗ Invalid task ID format[/red]")
            raise typer.Exit(1)

        db = get_database()
        await db.connect()
        try:
            service = DependencyService(db)

            data = TaskDependencyCreate(
                source_task_id=source_uuid,
                target_task_id=target_uuid,
                dependency_type=on,
            )

            try:
                result = await service.create_dependency(data)
                console.print(f"[green]✓ Added dependency: {source_id} → {target_id}[/green]")
                console.print(f"  Trigger: {on.value}")
            except ValueError as e:
                console.print(f"[red]✗ Error: {e}[/red]")
                raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_add())


@app.command("status")
def show_status(
    task_id: str = typer.Argument(..., help="Task ID to check"),
) -> None:
    async def _status():
        try:
            task_id_uuid = UUID(task_id)
        except ValueError:
            console.print(f"[red]✗ Invalid task ID format: {task_id}[/red]")
            raise typer.Exit(1)

        db = get_database()
        await db.connect()
        try:
            service = SchedulingService(db)
            task = await service.get_task(task_id_uuid)

            if not task:
                console.print(f"[red]✗ Task {task_id} not found[/red]")
                raise typer.Exit(1)

            console.print(f"[bold]Task: {task.name}[/bold]")
            console.print(f"  ID: {task.id}")
            console.print(f"  Scheduled: {task.is_scheduled}")
            console.print(f"  Cron: {task.cron_expression or 'None'}")
            console.print(f"  Next run: {task.next_run_at or 'N/A'}")
            console.print(f"  Last run: {task.last_run_at or 'Never'}")
            console.print(f"  Policy: {task.missed_run_policy}")
        finally:
            await db.disconnect()

    run_async(_status())
