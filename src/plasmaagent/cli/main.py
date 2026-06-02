"""Main CLI entry point using Typer."""

import asyncio
from typing import Optional

import typer

from plasmaagent import __version__
from plasmaagent.cli.logo import get_logo
from plasmaagent.cli.theme import console, style_info, style_success

app = typer.Typer(
    name="plasma",
    help="PlasmaAgent - Database-Centric Agentic Execution Framework",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Show version and exit.

    Args:
        value: Whether to show version
    """
    if value:
        console.print(f"[cyan]PlasmaAgent v{__version__}[/cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """PlasmaAgent - Database-Centric Agentic Execution Framework."""
    pass


@app.command()
def doctor() -> None:
    """Check system health and dependencies."""
    console.print(get_logo())
    console.print("\n[bold cyan]System Health Check[/bold cyan]\n")

    # Check Python version
    import sys

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"[cyan]✓[/cyan] Python: {python_version}")

    # Check database connection
    async def check_db() -> bool:
        try:
            from plasmaagent.core.database import get_database

            db = get_database()
            await db.connect()
            is_healthy = await db.health_check()
            await db.disconnect()
            return is_healthy
        except Exception as e:
            console.print(f"[magenta]✗[/magenta] Database: {e}")
            return False

    db_healthy = asyncio.run(check_db())
    if db_healthy:
        console.print("[cyan]✓[/cyan] Database: Connected")
    else:
        console.print("[magenta]✗[/magenta] Database: Connection failed")

    # Check schema
    async def check_schema() -> bool:
        try:
            from plasmaagent.core.database import get_database

            db = get_database()
            await db.connect()
            async with db.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'tasks'
                        )
                        """
                    )
                    result = await cur.fetchone()
            await db.disconnect()
            return result[0] if result else False
        except Exception:
            return False

    schema_ok = asyncio.run(check_schema())
    if schema_ok:
        console.print("[cyan]✓[/cyan] Schema: Initialized")
    else:
        console.print("[magenta]✗[/magenta] Schema: Not initialized (run 'make db-init')")

    console.print()


@app.command()
def hello() -> None:
    """Say hello (test command)."""
    console.print(style_success("Hello from PlasmaAgent!"))
    console.print(style_info("This is a test command."))


# Import and register task commands (lazy import to avoid circular dependency)
def register_commands() -> None:
    """Register subcommands."""
    from plasmaagent.cli import tasks

    app.add_typer(tasks.app, name="task", help="Task management commands")


# Register commands on module load
register_commands()


if __name__ == "__main__":
    app()
