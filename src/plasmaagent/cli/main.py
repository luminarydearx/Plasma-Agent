from typing import Optional

import typer

from plasmaagent import __version__
from plasmaagent.cli.logo import get_logo_centered
from plasmaagent.cli.theme import console, style_info, style_success
from plasmaagent.core.asyncio_compat import run_async

app = typer.Typer(
    name="plasma",
    help="PlasmaAgent - Database-Centric Agentic Execution Framework",
    invoke_without_command=True,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[#00D4FF]PlasmaAgent v{__version__}[/#00D4FF]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Ollama model name for chat mode",
    ),
    ollama_url: str = typer.Option(
        "http://localhost:11434",
        "--ollama-url",
        help="Ollama server URL",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        from plasmaagent.agent.repl import start_chat
        start_chat(model=model, base_url=ollama_url)


@app.command()
def chat(
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Ollama model name",
    ),
    ollama_url: str = typer.Option(
        "http://localhost:11434",
        "--ollama-url",
        help="Ollama server URL",
    ),
) -> None:
    """Start interactive AI chat session (same as running `plasma` with no args)."""
    from plasmaagent.agent.repl import start_chat
    start_chat(model=model, base_url=ollama_url)


@app.command()
def doctor() -> None:
    console.print(get_logo_centered())
    console.print("\n[bold #00D4FF]System Health Check[/bold #00D4FF]\n")

    import sys

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"[#00D4FF]✓[/#00D4FF] Python: {python_version}")

    async def check_all() -> tuple[bool, bool, bool]:
        from plasmaagent.core.database import get_database
        from plasmaagent.agent.ollama_client import OllamaClient

        db = get_database()
        ollama = OllamaClient()

        is_healthy = False
        schema_ok = False
        try:
            await db.connect()
            async with db.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1 AS ping")
                    health_result = await cur.fetchone()
                    if health_result is not None and health_result.get("ping") == 1:
                        is_healthy = True

                    await cur.execute(
                        """SELECT COUNT(*) AS table_count
                           FROM information_schema.tables
                           WHERE table_schema = 'public'
                             AND table_name IN ('tasks', 'task_steps', 'execution_logs', 'telemetry')"""
                    )
                    schema_result = await cur.fetchone()
                    if schema_result is not None and schema_result.get("table_count", 0) >= 4:
                        schema_ok = True
        except Exception:
            pass
        finally:
            if db._pool is not None:
                try:
                    await db.disconnect()
                except Exception:
                    pass

        ollama_ok = await ollama.health_check()
        return is_healthy, schema_ok, ollama_ok

    db_healthy, schema_ok, ollama_ok = run_async(check_all())

    if db_healthy:
        console.print("[#00D4FF]✓[/#00D4FF] Database: Connected")
    else:
        console.print("[bold #FF00D4]✗[/bold #FF00D4] Database: Connection failed")

    if schema_ok:
        console.print("[#00D4FF]✓[/#00D4FF] Schema: Initialized")
    else:
        console.print(
            "[bold #FF00D4]✗[/bold #FF00D4] Schema: Not initialized "
            "(run 'uv run alembic upgrade head')"
        )

    if ollama_ok:
        console.print("[#00D4FF]✓[/#00D4FF] Ollama: Reachable")
    else:
        console.print("[yellow]⚠[/yellow] Ollama: Not reachable at http://localhost:11434")

    console.print()


@app.command()
def hello() -> None:
    console.print(style_success("Hello from PlasmaAgent!"))
    console.print(style_info("This is a test command."))


def register_commands() -> None:
    from plasmaagent.cli import tasks
    from plasmaagent.cli import metrics
    from plasmaagent.cli import schedule
    from plasmaagent.cli import monitor
    from plasmaagent.cli import alerts
    from plasmaagent.cli import users
    from plasmaagent.cli import memory
    from plasmaagent.cli import files

    app.add_typer(tasks.app, name="task", help="Task management commands")
    app.add_typer(metrics.app, name="metrics", help="Template metrics and analytics")
    app.add_typer(schedule.app, name="schedule", help="Task scheduling commands")
    app.add_typer(monitor.monitor_app, name="monitor", help="Monitoring and observability commands")
    app.add_typer(alerts.alerts_app, name="alerts", help="Alert rules and notifications")
    app.add_typer(users.app, name="user", help="User management and audit commands")
    app.add_typer(memory.memory_app, name="memory", help="Memory system management")
    app.add_typer(files.file_app, name="file", help="File system operations")


register_commands()


if __name__ == "__main__":
    app()
