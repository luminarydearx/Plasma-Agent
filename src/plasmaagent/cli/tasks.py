"""Task management CLI commands."""

from typing import Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from plasmaagent.cli.theme import console, style_error, style_info, style_success
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import get_database
from plasmaagent.core.exceptions import PlasmaAgentError
from plasmaagent.models.task import TaskCreate
from plasmaagent.services.task_service import TaskService

app = typer.Typer(no_args_is_help=True)


@app.command("create")
def create_task(
    name: str = typer.Option(..., "--name", "-n", help="Task name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
) -> None:
    """Create a new task."""
    async def _create() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            task_data = TaskCreate(name=name, description=description)
            task = await service.create_task(task_data)
            await db.disconnect()
            console.print(style_success(f"Task created: {task.id}"))
            console.print(f"  Name: {task.name}")
            console.print(f"  Status: {task.status}")
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_create())


@app.command("list")
def list_tasks(
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by status"
    ),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum tasks to show"),
) -> None:
    """List all tasks."""
    async def _list() -> None:
        try:
            from plasmaagent.core.state_machine import TaskStatus

            db = get_database()
            await db.connect()
            service = TaskService(db)

            status_enum = None
            if status:
                try:
                    status_enum = TaskStatus(status.upper())
                except ValueError:
                    console.print(
                        style_error(
                            f"Invalid status: {status}. "
                            "Valid: PENDING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED"
                        )
                    )
                    raise typer.Exit(1)

            tasks = await service.list_tasks(status=status_enum, limit=limit)
            await db.disconnect()

            if not tasks:
                console.print(style_info("No tasks found"))
                return

            table = Table(title="Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Status", style="violet")
            table.add_column("Created", style="dim")

            for task in tasks:
                table.add_row(
                    str(task.id),
                    task.name,
                    task.status,
                    task.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_list())


@app.command("show")
def show_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    """Show task details."""
    async def _show() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.get_task(UUID(task_id))
            await db.disconnect()

            console.print(f"\n[bold cyan]Task Details[/bold cyan]\n")
            console.print(f"ID:          [white]{task.id}[/white]")
            console.print(f"Name:        [white]{task.name}[/white]")
            console.print(
                f"Description: [white]{task.description or 'N/A'}[/white]"
            )
            console.print(f"Status:      [violet]{task.status}[/violet]")
            console.print(
                f"Created:     [dim]{task.created_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
            )
            console.print(
                f"Updated:     [dim]{task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
            )
            console.print()
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_show())


@app.command("run")
def run_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    """Run a task (transition to RUNNING)."""
    async def _run() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.run_task(UUID(task_id))
            await db.disconnect()
            console.print(style_success(f"Task {task.id} is now RUNNING"))
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_run())


@app.command("cancel")
def cancel_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    """Cancel a task."""
    async def _cancel() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.cancel_task(UUID(task_id))
            await db.disconnect()
            console.print(style_success(f"Task {task.id} cancelled"))
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_cancel())


@app.command("retry")
def retry_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    """Retry a failed task."""
    async def _retry() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.retry_task(UUID(task_id))
            await db.disconnect()
            console.print(style_success(f"Task {task.id} reset to PENDING"))
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_retry())


@app.command("delete")
def delete_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a task."""
    if not force:
        confirm = typer.confirm(f"Delete task {task_id}?")
        if not confirm:
            raise typer.Abort()

    async def _delete() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)
            deleted = await service.delete_task(UUID(task_id))
            await db.disconnect()
            if deleted:
                console.print(style_success(f"Task {task_id} deleted"))
            else:
                console.print(style_error(f"Task {task_id} not found"))
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_delete())
