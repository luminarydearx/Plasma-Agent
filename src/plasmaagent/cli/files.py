import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from plasmaagent.cli.theme import console, pc

file_app = typer.Typer(
    name="file",
    help="File system operations with permission control",
    no_args_is_help=True,
)

ALLOWED_BASE_DIRS = {
    "documents": Path.home() / "Documents",
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "project": Path.cwd(),
}

DANGEROUS_DIRS = {
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    return path


def is_safe_path(path: Path) -> tuple[bool, str]:
    for dangerous in DANGEROUS_DIRS:
        try:
            path.relative_to(dangerous)
            return False, f"Access denied: {path} is in system directory"
        except ValueError:
            continue
    return True, "OK"


def confirm_operation(operation: str, path: Path, force: bool) -> bool:
    if force:
        return True
    console.print(f"\n[yellow]⚠ Permission Required[/yellow]")
    console.print(f"  Operation: {operation}")
    console.print(f"  Path: {path}")
    try:
        answer = input("  Proceed? [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


@file_app.command("create")
def create_file(
    path: str = typer.Argument(..., help="File path to create"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Initial content"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if exists"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    target = resolve_path(path)
    safe, msg = is_safe_path(target)
    if not safe:
        console.print(f"[bold red]✗ {msg}[/bold red]")
        raise typer.Exit(1)

    if target.exists() and not overwrite:
        console.print(f"[bold red]✗ File already exists: {target}[/bold red]")
        console.print("  Use --overwrite to replace it")
        raise typer.Exit(1)

    if not confirm_operation("CREATE", target, force):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    console.print(f"[bold green]✓ Created: {target}[/bold green]")


@file_app.command("read")
def read_file(
    path: str = typer.Argument(..., help="File path to read"),
    lines: Optional[int] = typer.Option(None, "--lines", "-n", help="Max lines to show"),
) -> None:
    target = resolve_path(path)
    safe, msg = is_safe_path(target)
    if not safe:
        console.print(f"[bold red]✗ {msg}[/bold red]")
        raise typer.Exit(1)

    if not target.exists():
        console.print(f"[bold red]✗ File not found: {target}[/bold red]")
        raise typer.Exit(1)

    if not target.is_file():
        console.print(f"[bold red]✗ Not a file: {target}[/bold red]")
        raise typer.Exit(1)

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        console.print(f"[bold red]✗ Binary file, cannot read as text[/bold red]")
        raise typer.Exit(1)

    if lines:
        content_lines = content.split("\n")[:lines]
        content = "\n".join(content_lines)

    console.print(Panel(
        content,
        title=f"[bold]{target.name}[/bold]",
        subtitle=f"{target} ({len(content)} chars)",
        border_style=pc("plasma_cyan"),
    ))


@file_app.command("write")
def write_file(
    path: str = typer.Argument(..., help="File path to write"),
    content: Optional[str] = typer.Option(None, "--content", "-c", help="Content to write"),
    append: bool = typer.Option(False, "--append", "-a", help="Append instead of overwrite"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    target = resolve_path(path)
    safe, msg = is_safe_path(target)
    if not safe:
        console.print(f"[bold red]✗ {msg}[/bold red]")
        raise typer.Exit(1)

    if content is None:
        console.print("[bold red]✗ --content is required[/bold red]")
        raise typer.Exit(1)

    operation = "APPEND" if append else "WRITE"
    if not confirm_operation(operation, target, force):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8") as f:
        f.write(content)

    console.print(f"[bold green]✓ {operation}: {target}[/bold green]")


@file_app.command("list")
def list_directory(
    path: str = typer.Argument(".", help="Directory path"),
    all_files: bool = typer.Option(False, "--all", "-a", help="Show hidden files"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="List recursively"),
) -> None:
    target = resolve_path(path)
    safe, msg = is_safe_path(target)
    if not safe:
        console.print(f"[bold red]✗ {msg}[/bold red]")
        raise typer.Exit(1)

    if not target.exists():
        console.print(f"[bold red]✗ Directory not found: {target}[/bold red]")
        raise typer.Exit(1)

    if not target.is_dir():
        console.print(f"[bold red]✗ Not a directory: {target}[/bold red]")
        raise typer.Exit(1)

    table = Table(
        title=f"Contents: {target}",
        border_style=pc("plasma_cyan"),
        header_style=f"bold {pc('solar_gold')}",
    )
    table.add_column("Type", style=pc("plasma_magenta"), width=6)
    table.add_column("Name", style=pc("plasma_cyan"))
    table.add_column("Size", justify="right", style=pc("aurora_green"))
    table.add_column("Modified", style=pc("plasma_violet"))

    if recursive:
        items = sorted(target.rglob("*"))
    else:
        items = sorted(target.iterdir())

    count = 0
    for item in items:
        if not all_files and item.name.startswith("."):
            continue

        item_type = "DIR" if item.is_dir() else "FILE"
        try:
            size = item.stat().st_size if item.is_file() else 0
            size_str = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB"
        except OSError:
            size_str = "?"

        try:
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
        except OSError:
            mtime_str = "?"

        table.add_row(item_type, str(item.relative_to(target)), size_str, mtime_str)
        count += 1

    console.print(table)
    console.print(f"\n[dim]{count} items[/dim]")


@file_app.command("delete")
def delete_file(
    path: str = typer.Argument(..., help="File or directory to delete"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Delete directory recursively"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    target = resolve_path(path)
    safe, msg = is_safe_path(target)
    if not safe:
        console.print(f"[bold red]✗ {msg}[/bold red]")
        raise typer.Exit(1)

    if not target.exists():
        console.print(f"[bold red]✗ Not found: {target}[/bold red]")
        raise typer.Exit(1)

    if not confirm_operation("DELETE", target, force):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    if target.is_dir():
        if not recursive:
            console.print("[bold red]✗ Use --recursive to delete directories[/bold red]")
            raise typer.Exit(1)
        import shutil
        shutil.rmtree(target)
    else:
        target.unlink()

    console.print(f"[bold green]✓ Deleted: {target}[/bold green]")


@file_app.command("info")
def file_info(
    path: str = typer.Argument(..., help="File or directory path"),
) -> None:
    target = resolve_path(path)
    if not target.exists():
        console.print(f"[bold red]✗ Not found: {target}[/bold red]")
        raise typer.Exit(1)

    stat = target.stat()
    info_table = Table(
        title=f"Info: {target.name}",
        border_style=pc("plasma_cyan"),
        show_header=False,
    )
    info_table.add_column("Property", style=pc("solar_gold"))
    info_table.add_column("Value", style=pc("plasma_cyan"))

    info_table.add_row("Path", str(target))
    info_table.add_row("Type", "Directory" if target.is_dir() else "File")
    info_table.add_row("Size", f"{stat.st_size:,} bytes")
    info_table.add_row("Created", datetime.fromtimestamp(stat.st_ctime).isoformat())
    info_table.add_row("Modified", datetime.fromtimestamp(stat.st_mtime).isoformat())
    info_table.add_row("Accessed", datetime.fromtimestamp(stat.st_atime).isoformat())
    info_table.add_row("Permissions", oct(stat.st_mode)[-3:])

    console.print(info_table)


@file_app.command("execute")
def execute_command(
    command: str = typer.Argument(..., help="PowerShell/CMD command to execute"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    import subprocess

    dangerous_patterns = [
        "rm -rf", "format", "del /s", "rmdir /s",
        "DROP TABLE", "DROP DATABASE", "shutdown",
    ]
    for pattern in dangerous_patterns:
        if pattern.lower() in command.lower():
            console.print(f"[bold red]✗ Dangerous command detected: {pattern}[/bold red]")
            if not force:
                raise typer.Exit(1)

    if not confirm_operation("EXECUTE", Path(command[:50]), force):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    console.print(f"[dim]Executing: {command}[/dim]\n")

    shell_name = "powershell" if sys.platform == "win32" else "bash"
    shell_flag = "-Command" if sys.platform == "win32" else "-c"

    result = subprocess.run(
        [shell_name, shell_flag, command],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(f"[red]{result.stderr}[/red]")

    console.print(f"\n[dim]Exit code: {result.returncode}[/dim]")
