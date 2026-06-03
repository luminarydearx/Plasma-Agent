import asyncio
import sys
from typing import Optional
from uuid import UUID

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from plasmaagent.cli.theme import console, style_error, style_info, style_success
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import get_database
from plasmaagent.core.exceptions import PlasmaAgentError
from plasmaagent.executor.result import ExecutionResult, OutputChunk, OutputSource
from plasmaagent.models.task import TaskCreate, TaskPayload
from plasmaagent.services.execution_service import ExecutionService
from plasmaagent.services.task_service import TaskService

app = typer.Typer(no_args_is_help=True)

MAX_INPUT_LENGTH = 10000


def _is_interactive_terminal() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _validate_natural_language_input(value: Optional[str]) -> str:
    if value is None:
        if not _is_interactive_terminal():
            raise typer.BadParameter(
                "No input provided. Use --input \"your task description\" "
                "or run in an interactive terminal."
            )
        prompted = typer.prompt("Describe the task in natural language")
        value = prompted

    if not isinstance(value, str):
        raise typer.BadParameter(
            f"Input must be a string, got {type(value).__name__}"
        )

    if len(value) > MAX_INPUT_LENGTH:
        raise typer.BadParameter(
            f"Input too long ({len(value)} chars). "
            f"Maximum is {MAX_INPUT_LENGTH} characters."
        )

    stripped = value.strip()
    if not stripped:
        raise typer.BadParameter(
            "Input cannot be empty or whitespace only. "
            "Please provide a meaningful task description."
        )

    null_bytes = stripped.count("\x00")
    if null_bytes > 0:
        raise typer.BadParameter(
            f"Input contains {null_bytes} null byte(s) which is not allowed."
        )

    return stripped


@app.command("create")
def create_task(
    name: str = typer.Option(..., "--name", "-n", help="Task name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Task description"
    ),
    command: Optional[list[str]] = typer.Option(
        None, "--command", "-c", help="Shell command to execute (repeatable)"
    ),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Execution timeout (s)"),
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    async def _create() -> None:
        try:
            db = get_database()
            await db.connect()
            service = TaskService(db)

            payload: Optional[TaskPayload] = None
            if command:
                payload = TaskPayload(
                    commands=command,
                    timeout=timeout,
                    cwd=cwd,
                )

            task_data = TaskCreate(
                name=name,
                description=description,
                payload=payload,
            )
            task = await service.create_task(task_data)
            await db.disconnect()

            lines = [
                f"[#00D4FF]ID:[/#00D4FF]     {task.id}",
                f"[#00D4FF]Name:[/#00D4FF]   {task.name}",
                f"[#00D4FF]Status:[/#00D4FF] [#00FF7F]{task.status}[/#00FF7F]",
            ]
            if task.description:
                lines.append(f"[#00D4FF]Desc:[/#00D4FF]   {task.description}")
            if command:
                lines.append(
                    f"[#00D4FF]Steps:[/#00D4FF]  {len(command)} command(s)"
                )
                for idx, cmd in enumerate(command, start=1):
                    lines.append(f"  [#FFD700]{idx}.[/#FFD700] {cmd}")

            content = "\n".join(lines)
            panel = Panel(
                content,
                title="[bold #FFD700]Task Created[/bold #FFD700]",
                border_style="#00D4FF",
                padding=(1, 2),
            )
            console.print(panel)
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

            table = Table(title="[bold #FFD700]Tasks[/bold #FFD700]", border_style="#00D4FF")
            table.add_column("ID", style="#00D4FF")
            table.add_column("Name", style="#F0F8FF")
            table.add_column("Status", style="#8B00FF")
            table.add_column("Created", style="dim")

            status_colors = {
                "PENDING": "#FFD700",
                "RUNNING": "#00D4FF",
                "COMPLETED": "#00FF7F",
                "FAILED": "#FF00D4",
                "CANCELLED": "#FF1493",
                "PAUSED": "#8B00FF",
            }

            for task in tasks:
                color = status_colors.get(task.status, "#FFFFFF")
                table.add_row(
                    str(task.id),
                    task.name,
                    f"[{color}]{task.status}[/{color}]",
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
    show_steps: bool = typer.Option(False, "--steps", help="Show execution steps"),
    show_logs: bool = typer.Option(False, "--logs", help="Show execution logs"),
) -> None:
    async def _show() -> None:
        try:
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                console.print(style_error(f"Invalid task ID format: {task_id}"))
                raise typer.Exit(1)

            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.get_task(task_uuid)

            if not task:
                console.print(style_error(f"Task not found: {task_id}"))
                await db.disconnect()
                raise typer.Exit(1)

            status_colors = {
                "PENDING": "#FFD700",
                "RUNNING": "#00D4FF",
                "COMPLETED": "#00FF7F",
                "FAILED": "#FF00D4",
                "CANCELLED": "#FF1493",
                "PAUSED": "#8B00FF",
            }
            color = status_colors.get(task.status, "#FFFFFF")

            content = (
                f"[#00D4FF]ID:[/#00D4FF]          {task.id}\n"
                f"[#00D4FF]Name:[/#00D4FF]        {task.name}\n"
                f"[#00D4FF]Description:[/#00D4FF] {task.description or 'N/A'}\n"
                f"[#00D4FF]Status:[/#00D4FF]      [{color}]{task.status}[/{color}]\n"
                f"[#00D4FF]Created:[/#00D4FF]     {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"[#00D4FF]Updated:[/#00D4FF]     {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if task.payload:
                commands = task.payload.get("commands", [])
                if commands:
                    content += "\n\n[#FFD700]Commands:[/#FFD700]"
                    for idx, cmd in enumerate(commands, start=1):
                        content += f"\n  [#FFD700]{idx}.[/#FFD700] {cmd}"

            panel = Panel(
                content,
                title="[bold #FFD700]Task Details[/bold #FFD700]",
                border_style="#00D4FF",
                padding=(1, 2),
            )
            console.print()
            console.print(panel)

            if show_steps:
                steps = await service.get_task_steps(task_uuid)
                if steps:
                    console.print()
                    steps_table = Table(
                        title="[bold #FFD700]Execution Steps[/bold #FFD700]",
                        border_style="#00D4FF",
                    )
                    steps_table.add_column("#", style="#FFD700", justify="right")
                    steps_table.add_column("Command", style="#F0F8FF")
                    steps_table.add_column("Status", style="#8B00FF")
                    steps_table.add_column("Exit", justify="right")
                    steps_table.add_column("Duration", justify="right", style="dim")

                    for step in steps:
                        step_color = status_colors.get(step["status"], "#FFFFFF")
                        exit_str = (
                            str(step["exit_code"])
                            if step["exit_code"] is not None
                            else "-"
                        )
                        duration_str = (
                            f"{step['duration_ms']}ms"
                            if step["duration_ms"] is not None
                            else "-"
                        )
                        steps_table.add_row(
                            str(step["step_order"]),
                            step["command"][:60],
                            f"[{step_color}]{step['status']}[/{step_color}]",
                            exit_str,
                            duration_str,
                        )
                    console.print(steps_table)
                else:
                    console.print("\n" + style_info("No execution steps yet"))

            if show_logs:
                logs = await service.get_execution_logs(task_uuid)
                if logs:
                    console.print()
                    log_text = Text()
                    for log in logs[-50:]:
                        level_color = {
                            "INFO": "#00D4FF",
                            "STDOUT": "#00FF7F",
                            "STDERR": "#FF00D4",
                            "ERROR": "#FF00D4",
                        }.get(log["log_level"], "#FFFFFF")
                        log_text.append(
                            f"[{log['log_level']}] ",
                            style=f"bold {level_color}",
                        )
                        log_text.append(f"{log['message']}\n")
                    log_panel = Panel(
                        log_text,
                        title="[bold #FFD700]Execution Logs[/bold #FFD700]",
                        border_style="#8B00FF",
                        padding=(1, 2),
                    )
                    console.print(log_panel)
                else:
                    console.print("\n" + style_info("No execution logs yet"))

            await db.disconnect()
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_show())


@app.command("run")
def run_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream output"),
) -> None:
    async def _run() -> None:
        try:
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                console.print(style_error(f"Invalid task ID format: {task_id}"))
                raise typer.Exit(1)

            db = get_database()
            await db.connect()
            task_service = TaskService(db)
            execution_service = ExecutionService(db)

            task = await task_service.get_task(task_uuid)

            if not task:
                console.print(style_error(f"Task not found: {task_id}"))
                await db.disconnect()
                raise typer.Exit(1)

            if not task.payload or not task.payload.get("commands"):
                console.print(
                    style_error(
                        f"Task {task_id} has no commands. "
                        "Use --command when creating a task."
                    )
                )
                await db.disconnect()
                raise typer.Exit(1)

            console.print()
            console.print(
                f"[bold #00D4FF]Executing:[/bold #00D4FF] {task.name}",
            )
            console.print(
                f"[bold #00D4FF]Commands:[/bold #00D4FF] "
                f"{len(task.payload['commands'])} step(s)\n",
            )

            current_step: list[int] = [0]

            async def _on_step_start(step_order: int, command: str) -> None:
                current_step[0] = step_order
                console.print(
                    f"\n[bold #FFD700]▶ Step {step_order}:[/bold #FFD700] "
                    f"[#F0F8FF]{command}[/#F0F8FF]"
                )
                console.print("[dim]" + "─" * 60 + "[/dim]")

            async def _on_step_output(step_order: int, chunk: OutputChunk) -> None:
                if not stream:
                    return
                color = "#00FF7F" if chunk.source == OutputSource.STDOUT else "#FF00D4"
                for line in chunk.data.splitlines():
                    console.print(f"  [{color}]{line}[/{color}]", markup=False)

            async def _on_step_complete(step_order: int, result: ExecutionResult) -> None:
                console.print("[dim]" + "─" * 60 + "[/dim]")
                if result.succeeded:
                    console.print(
                        f"  [#00FF7F]✓ Step {step_order} completed[/#00FF7F] "
                        f"[dim]({result.duration_ms}ms, exit={result.exit_code})[/dim]"
                    )
                else:
                    console.print(
                        f"  [#FF00D4]✗ Step {step_order} failed[/#FF00D4] "
                        f"[dim]({result.duration_ms}ms, exit={result.exit_code})[/dim]"
                    )
                    if result.stderr:
                        console.print(
                            f"  [#FF00D4]stderr:[/#FF00D4] {result.stderr[:500]}",
                            markup=False,
                        )

            final_task = await execution_service.execute_task(
                task_uuid,
                on_step_start=_on_step_start,
                on_step_output=_on_step_output,
                on_step_complete=_on_step_complete,
            )

            await db.disconnect()

            console.print()
            status_color = "#00FF7F" if final_task.status == "COMPLETED" else "#FF00D4"
            content = (
                f"[#00D4FF]ID:[/#00D4FF]     {final_task.id}\n"
                f"[#00D4FF]Status:[/#00D4FF] [{status_color}]{final_task.status}[/{status_color}]"
            )
            title_color = "#00FF7F" if final_task.status == "COMPLETED" else "#FF00D4"
            panel = Panel(
                content,
                title=f"[bold {title_color}]Execution {final_task.status}[/bold {title_color}]",
                border_style=title_color,
                padding=(1, 2),
            )
            console.print(panel)

            if final_task.status == "FAILED":
                raise typer.Exit(1)

        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_run())


@app.command("cancel")
def cancel_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    async def _cancel() -> None:
        try:
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                console.print(style_error(f"Invalid task ID format: {task_id}"))
                raise typer.Exit(1)

            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.cancel_task(task_uuid)
            await db.disconnect()

            content = (
                f"[#00D4FF]ID:[/#00D4FF]     {task.id}\n"
                f"[#00D4FF]Status:[/#00D4FF] [#FF1493]{task.status}[/#FF1493]"
            )
            panel = Panel(
                content,
                title="[bold #FFD700]Task Cancelled[/bold #FFD700]",
                border_style="#FFD700",
                padding=(1, 2),
            )
            console.print(panel)
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_cancel())


@app.command("retry")
def retry_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
) -> None:
    async def _retry() -> None:
        try:
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                console.print(style_error(f"Invalid task ID format: {task_id}"))
                raise typer.Exit(1)

            db = get_database()
            await db.connect()
            service = TaskService(db)
            task = await service.retry_task(task_uuid)
            await db.disconnect()

            content = (
                f"[#00D4FF]ID:[/#00D4FF]     {task.id}\n"
                f"[#00D4FF]Status:[/#00D4FF] [#FFD700]{task.status}[/#FFD700]"
            )
            panel = Panel(
                content,
                title="[bold #00FF7F]Task Queued for Retry[/bold #00FF7F]",
                border_style="#00FF7F",
                padding=(1, 2),
            )
            console.print(panel)
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_retry())


@app.command("delete")
def delete_task(
    task_id: str = typer.Option(..., "--id", "-i", help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    if not force:
        if not _is_interactive_terminal():
            console.print(
                style_error(
                    "Non-interactive mode requires --force flag to delete tasks. "
                    "Use: plasma task delete --id <ID> --force"
                )
            )
            raise typer.Exit(1)
        confirm = typer.confirm(f"Delete task {task_id}?")
        if not confirm:
            raise typer.Abort()

    async def _delete() -> None:
        try:
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                console.print(style_error(f"Invalid task ID format: {task_id}"))
                raise typer.Exit(1)

            db = get_database()
            await db.connect()
            service = TaskService(db)
            deleted = await service.delete_task(task_uuid)
            await db.disconnect()

            if deleted:
                content = (
                    f"[#FF00D4]ID:[/#FF00D4]     {task_id}\n"
                    f"[#FF00D4]Status:[/#FF00D4] DELETED"
                )
                panel = Panel(
                    content,
                    title="[bold #FF00D4]Task Deleted[/bold #FF00D4]",
                    border_style="#FF00D4",
                    padding=(1, 2),
                )
                console.print(panel)
            else:
                console.print(style_error(f"Task {task_id} not found"))
        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

    run_async(_delete())


@app.command("generate")
def generate_task(
    natural_language: Optional[str] = typer.Option(
        None, "--input", "-i", help="Natural language description"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Provider to use (default: rule_based)"
    ),
    preview_only: bool = typer.Option(
        False, "--preview", help="Only show preview, don't create task"
    ),
    auto_confirm: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    async def _generate() -> None:
        from plasmaagent.services.task_generator import TaskGeneratorService
        from plasmaagent.ai.providers import get_provider

        try:
            natural_language_input = _validate_natural_language_input(natural_language)
        except typer.BadParameter as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)

        if provider is not None:
            try:
                get_provider(provider)
            except ValueError as e:
                console.print(style_error(f"Error: {e}"))
                raise typer.Exit(1)

        db = get_database()
        try:
            await db.connect()
            generator_service = TaskGeneratorService(db)

            console.print()
            console.print(
                f"[bold #00D4FF]Generating task from:[/bold #00D4FF] "
                f"[#F0F8FF]{natural_language_input}[/#F0F8FF]"
            )
            console.print()

            response = await generator_service.generate_from_natural_language(
                natural_language=natural_language_input,
                provider_name=provider,
                context={},
            )

            if not response.tasks:
                console.print(
                    style_error(
                        "Could not generate task from input. "
                        "Try being more specific or use 'plasma task create' for manual creation."
                    )
                )
                raise typer.Exit(1)

            generated = response.tasks[0]

            preview_text = generator_service.preview_task(generated)
            preview_panel = Panel(
                preview_text,
                title="[bold #FFD700]Generated Task Preview[/bold #FFD700]",
                border_style="#FFD700",
                padding=(1, 2),
            )
            console.print(preview_panel)
            console.print()

            console.print(
                f"[dim]Provider: {response.provider_used}[/dim]"
            )
            console.print(
                f"[dim]Time: {response.total_time_ms:.1f}ms[/dim]"
            )
            console.print()

            if preview_only:
                return

            if not auto_confirm:
                if not _is_interactive_terminal():
                    console.print(
                        style_error(
                            "Non-interactive mode requires --yes flag to create tasks. "
                            "Use: plasma task generate --input \"...\" --yes"
                        )
                    )
                    raise typer.Exit(1)
                confirm = typer.confirm("Create this task?")
                if not confirm:
                    console.print(style_info("Task creation cancelled"))
                    raise typer.Abort()

            task_id = await generator_service.create_task_from_generation(generated)

            content = (
                f"[#00D4FF]ID:[/#00D4FF]       {task_id}\n"
                f"[#00D4FF]Name:[/#00D4FF]     {generated.name}\n"
                f"[#00D4FF]Status:[/#00D4FF]   [#00FF7F]PENDING[/#00FF7F]\n"
                f"[#00D4FF]Commands:[/#00D4FF] {len(generated.commands)} step(s)"
            )
            panel = Panel(
                content,
                title="[bold #00FF7F]Task Created from AI[/bold #00FF7F]",
                border_style="#00FF7F",
                padding=(1, 2),
            )
            console.print(panel)
            console.print()
            console.print(
                style_info(f"Run with: plasma task run --id {task_id}")
            )

        except PlasmaAgentError as e:
            console.print(style_error(f"Error: {e}"))
            raise typer.Exit(1)
        except typer.Exit:
            raise
        except typer.Abort:
            raise
        except Exception as e:
            console.print(style_error(f"Unexpected error: {e}"))
            raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_generate())
