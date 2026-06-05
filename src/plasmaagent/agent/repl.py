"""Interactive REPL chat interface for PlasmaAgent."""

from __future__ import annotations

import asyncio
import html
import os
import signal
import sys
import time
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.status import Status

if TYPE_CHECKING:
    from plasmaagent.agent.ollama_client import OllamaClient
    from plasmaagent.agent.orchestrator import AgentOrchestrator

console = Console()


def _short_model(name: str) -> str:
    base = name.split(":")[0] if ":" in name else name
    if "/" in base:
        base = base.split("/")[-1]
    parts = base.replace("_", "-").split("-")
    if len(parts) <= 3:
        return base
    return "-".join(parts[:3])


def _render_tool_call(name: str, args: dict, result: str) -> None:
    arg_preview = ", ".join(f"{k}={_truncate(str(v), 40)}" for k, v in args.items())
    console.print(f"[dim]  → {name}({arg_preview})[/dim]")
    result_preview = _truncate(str(result), 200)
    if result.startswith("✓"):
        console.print(f"[green]  {result_preview}[/green]")
    elif result.startswith("✗"):
        console.print(f"[red]  {result_preview}[/red]")
    else:
        console.print(Panel(result_preview, title=f"[cyan]{name}[/cyan]", expand=False))


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def print_banner(model: str, base_url: str, username: str, tools_count: int) -> None:
    logo_lines = [
        "██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗ ",
        "██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗",
        "██████╔╝██║     ███████║███████╗██╔████╔██║███████║",
        "██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║",
        "██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║",
        "╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝",
    ]
    logo = "\n".join(logo_lines)

    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80
    logo_width = max(len(line) for line in logo_lines)
    box_inner = term_width - 4
    if box_inner < logo_width + 4:
        box_inner = logo_width + 4
    padding = max(0, (box_inner - logo_width) // 2)

    centered = "\n".join(f"{' ' * padding}{line}" for line in logo_lines)
    centered += "\n\n"
    agent_line = "       ╭─────╮  AGENT  ╭─────╮"
    ver_line = "       │ @@@ │  v0.1.0 │ @@@ │"
    bot_line = "       ╰─────╯         ╰─────╯"
    centered += f"{' ' * padding}{agent_line}\n"
    centered += f"{' ' * padding}{ver_line}\n"
    centered += f"{' ' * padding}{bot_line}"

    info = (
        f"  PlasmaAgent Interactive Chat\n"
        f"  User:  [bold cyan]{username}[/bold cyan]\n"
        f"  Model: [green]{model}[/green]\n"
        f"  Ollama:[blue]{base_url}[/blue]\n"
        f"  Tools: [yellow]{tools_count} loaded[/yellow]\n"
        f"\n"
        f"  Commands:\n"
        f"    [cyan]exit/quit[/cyan]  - Leave chat\n"
        f"    [cyan]/clear[/cyan]    - Clear screen & chat\n"
        f"    [cyan]/reset[/cyan]    - Clear history only\n"
        f"    [cyan]/tools[/cyan]    - List available tools\n"
        f"    [cyan]/model[/cyan]    - List models (with ctx)\n"
        f"    [cyan]/model <n>[/cyan]- Switch model (saved for next session)\n"
        f"    [cyan]/perms[/cyan]    - View saved permissions\n"
        f"    [cyan]/perms reset[/cyan] - Reset all permissions\n"
        f"    [cyan]Ctrl+C[/cyan]    - Cancel current operation"
    )

    console.print(Panel(centered + "\n\n" + info, border_style="blue", expand=True))


async def _handle_model_command(
    query: str, ollama: "OllamaClient", orchestrator: "AgentOrchestrator"
) -> None:
    from plasmaagent.agent.config_manager import set_default_model

    parts = query.strip().split(maxsplit=1)
    if len(parts) == 1:
        models = await ollama.list_models()
        if not models:
            console.print("[yellow]No models found in Ollama.[/yellow]")
            return
        current = ollama._model
        table = Table(title="Available Models", show_header=False, box=None)
        for m in models:
            marker = " [bold green]← current[/bold green]" if m["name"] == current else ""
            size = f" ({m['size_gb']:.1f} GB"
            if m.get("context_length"):
                size += f" | ctx: {m['context_length']:,}"
            size += ")"
            table.add_row(f"[cyan]{m['name']}[/cyan]{size}{marker}")
        console.print(table)
        console.print("[dim]Usage: /model <name> to switch (auto-saved)[/dim]")
        return

    new_model = parts[1].strip()
    models = await ollama.list_models()
    names = [m["name"] for m in models]
    if new_model not in names:
        console.print(f"[red]Model '{new_model}' not found.[/red]")
        console.print(f"[dim]Available: {', '.join(names)}[/dim]")
        return

    await ollama.set_model(new_model)
    set_default_model(new_model)
    orchestrator._history.clear()
    console.print(f"[green]Switched to: {new_model}[/green]")
    console.print(f"[green]Saved as default for next session.[/green]")
    console.print("[dim]History cleared.[/dim]")


async def _handle_perms_command(query: str, orchestrator: "AgentOrchestrator") -> None:
    from plasmaagent.agent.permission_manager import list_permissions
    
    parts = query.strip().split()

    if len(parts) >= 2 and parts[1].lower() == "reset":
        from plasmaagent.agent.permission_manager import reset_permissions
        reset_permissions()
        console.print("[green]All permissions reset.[/green]")
        return

    perms = list_permissions()
    tool_perms = perms.get("tools", {})
    if not tool_perms:
        console.print("[dim]No saved permissions yet.[/dim]")
        return

    table = Table(title="Saved Permissions", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Decision", style="green")
    for tool, decision in sorted(tool_perms.items()):
        table.add_row(tool, decision)
    console.print(table)


async def _chat_loop(orchestrator: "AgentOrchestrator", username: str, base_url: str) -> None:
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.formatted_text import HTML
    except ImportError:
        console.print("[yellow]prompt_toolkit not installed. Using fallback input.[/yellow]")
        _chat_loop_fallback(orchestrator)
        return

    session: Any = PromptSession(history=InMemoryHistory())
    
    status_handle: Status | None = None
    spinner_active = False
    cancel_requested = False
    
    def stop_spinner() -> None:
        nonlocal status_handle, spinner_active
        if spinner_active and status_handle is not None:
            status_handle.stop()
            spinner_active = False
    
    def start_spinner() -> None:
        nonlocal status_handle, spinner_active
        if not spinner_active:
            status_handle = console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots")
            status_handle.start()
            spinner_active = True
    
    def request_cancel() -> None:
        nonlocal cancel_requested
        cancel_requested = True
        stop_spinner()
    
    orchestrator._on_permission_needed = stop_spinner
    orchestrator._on_permission_done = start_spinner
    orchestrator._cancel_callback = request_cancel

    while True:
        model = orchestrator._ollama._model
        short = _short_model(model)
        safe_username = _escape_xml(username)
        safe_short = _escape_xml(short)
        prompt_label = HTML(
            f"\n<b><style fg='ansicyan'>{safe_username}</style>"
            f"<style fg='ansimagenta'>@[{safe_short}]</style></b>"
            f"<style fg='gray'> &gt; </style>"
        )

        try:
            user_input = await asyncio.to_thread(
                session.prompt, prompt_label,
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            return

        if not user_input:
            continue

        cmd = user_input.strip()
        if cmd.lower() in {"exit", "quit", "keluar"}:
            console.print("[yellow]Goodbye![/yellow]")
            return

        if cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            orchestrator._history.clear()
            print_banner(model, base_url, username, len(orchestrator._tools))
            continue

        if cmd == "/reset":
            orchestrator._history.clear()
            console.print("[green]History cleared.[/green]")
            continue

        if cmd == "/tools":
            table = Table(title="Available Tools", show_header=False, box=None)
            for name, tool in sorted(orchestrator._tools.items()):
                desc = tool.description.split("\n")[0] if tool.description else ""
                table.add_row(f"[cyan]{name}[/cyan]", f"[dim]{desc}[/dim]")
            console.print(table)
            continue

        if cmd.startswith("/model"):
            await _handle_model_command(cmd, orchestrator._ollama, orchestrator)
            continue

        if cmd.startswith("/perms"):
            await _handle_perms_command(cmd, orchestrator)
            continue

        start = time.time()
        cancel_requested = False
        
        try:
            start_spinner()
            
            async def chat_with_cancel():
                nonlocal cancel_requested
                task = asyncio.create_task(orchestrator.chat(user_input))
                
                while not task.done():
                    if cancel_requested:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        return None
                    await asyncio.sleep(0.1)
                
                return await task
            
            response = await chat_with_cancel()
            stop_spinner()
            
            if cancel_requested:
                console.print("[yellow]Operation cancelled.[/yellow]")
                continue
                
        except asyncio.CancelledError:
            stop_spinner()
            console.print("[yellow]Operation cancelled.[/yellow]")
            continue
        except KeyboardInterrupt:
            stop_spinner()
            console.print("[yellow]Operation cancelled.[/yellow]")
            continue
        except Exception as e:
            stop_spinner()
            elapsed = time.time() - start
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]⏱ {:.1f}s[/dim]".format(elapsed))
            continue

        elapsed = time.time() - start

        if response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get("name") or tc.get("function", {}).get("name", "unknown")
                tool_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                result = await orchestrator.execute_tool(tool_name, tool_args)
                _render_tool_call(tool_name, tool_args, result)
            console.print()

        if response.text:
            try:
                console.print(Markdown(response.text))
            except Exception:
                console.print(response.text)

        console.print(f"[dim]⏱ {elapsed:.1f}s[/dim]")


def _chat_loop_fallback(orchestrator: "AgentOrchestrator") -> None:
    console.print("[dim](Using basic input - install prompt_toolkit for better UX)[/dim]")
    while True:
        try:
            user_input = input("\n[you] > ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            return

        if not user_input:
            continue
        if user_input.strip().lower() in {"exit", "quit"}:
            console.print("[yellow]Goodbye![/yellow]")
            return

        async def run():
            response = await orchestrator.chat(user_input)
            if response.tool_calls:
                for tc in response.tool_calls:
                    tool_name = tc.get("name") or tc.get("function", {}).get("name", "unknown")
                    tool_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                    result = await orchestrator.execute_tool(tool_name, tool_args)
                    _render_tool_call(tool_name, tool_args, result)
            if response.text:
                console.print(response.text)

        asyncio.run(run())


def start_chat(model: str = "qwen2.5-coder:7b-instruct", base_url: str = "http://localhost:11434") -> None:
    from plasmaagent.agent.config_manager import get_default_model, set_default_model
    from plasmaagent.agent.ollama_client import OllamaClient
    from plasmaagent.agent.orchestrator import AgentOrchestrator

    async def main():
        from plasmaagent.core.database import get_database
        from plasmaagent.core.schema import init_schema
        
        db = get_database()
        await db.connect()
        async with db.connection() as conn:
            await init_schema(conn)
        
        ollama = OllamaClient(model=model, base_url=base_url)

        saved_model = get_default_model()
        if saved_model:
            await ollama.set_model(saved_model)
            selected_model = saved_model
        else:
            models = await ollama.list_models()
            if models:
                auto_model = models[0]["name"]
                await ollama.set_model(auto_model)
                set_default_model(auto_model)
                selected_model = auto_model
            else:
                console.print("[red]No models found in Ollama. Run: ollama pull qwen2.5-coder:7b-instruct[/red]")
                return
            available = await ollama.list_models()
            available_names = [m["name"] for m in available]
            if selected_model not in available_names:
                if available:
                    fallback = available[0]["name"]
                    await ollama.set_model(fallback)
                    set_default_model(fallback)
                    selected_model = fallback
                    console.print(f"[yellow]Model '{model}' not found. Using: {fallback}[/yellow]")

        username = os.environ.get("USERNAME") or os.environ.get("USER") or "User"
        try:
            import getpass
            username = getpass.getuser()
        except Exception:
            pass

        print_banner(selected_model, base_url, username, len(TOOL_REGISTRY))

        orchestrator = AgentOrchestrator(ollama=ollama)
        await _chat_loop(orchestrator, username, base_url)

    from plasmaagent.core.asyncio_compat import run_async
    run_async(main())


from plasmaagent.agent.tools import TOOL_REGISTRY
