from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.orchestrator import AgentOrchestrator
from plasmaagent.cli.logo import get_logo_centered
from plasmaagent.core.asyncio_compat import run_async


console = Console()

ANSI_CYAN = "\033[36m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"


def _get_username() -> str:
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "user"


def _print_tool_call(name: str, args: dict[str, Any]) -> None:
    args_str = ", ".join(f"{k}={_json_truncate(v)}" for k, v in args.items())
    console.print(f"  [magenta]→[/magenta] [bold]{name}[/bold]({args_str})")


def _print_tool_result(name: str, success: bool, output: str) -> None:
    marker = "[green]✓[/green]" if success else "[red]✗[/red]"
    preview = output.replace("\n", " ")[:200]
    if len(output) > 200:
        preview += "..."
    console.print(f"  {marker} [dim]{name}:[/dim] {preview}")


def _json_truncate(value: Any, max_len: int = 60) -> str:
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def print_banner(model: str, ollama_url: str, username: str) -> None:
    console.print(get_logo_centered())
    console.print(Panel.fit(
        f"[bold #00D4FF]PlasmaAgent Interactive Chat[/bold #00D4FF]\n"
        f"[dim]User:[/dim] [cyan]{username}[/cyan]\n"
        f"[dim]Model:[/dim] [cyan]{model}[/cyan]\n"
        f"[dim]Ollama:[/dim] [cyan]{ollama_url}[/cyan]\n"
        f"[dim]Commands:[/dim]\n"
        f"  [cyan]exit/quit[/cyan] - Leave chat\n"
        f"  [cyan]/reset[/cyan] - Clear history\n"
        f"  [cyan]/tools[/cyan] - List available tools",
        border_style="#00D4FF",
    ))


def print_tools() -> None:
    from plasmaagent.agent.tools import TOOL_REGISTRY
    lines = []
    for name, tool in TOOL_REGISTRY.items():
        lines.append(f"[bold cyan]{name}[/bold cyan]\n  {tool.description}")
    console.print(Panel("\n".join(lines), title="Available Tools", border_style="#00D4FF"))


async def _health_check(ollama: OllamaClient) -> bool:
    return await ollama.health_check()


async def _chat_loop(orchestrator: AgentOrchestrator, username: str) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.formatted_text import HTML

    session: Any = PromptSession(history=InMemoryHistory())
    prompt_label = HTML(f"\n<b><style fg='ansicyan'>{username}</style></b><style fg='gray'> &gt; </style>")

    while True:
        try:
            user_input = await asyncio.to_thread(
                session.prompt, prompt_label,
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            console.print("[yellow]Goodbye![/yellow]")
            break
        if user_input == "/reset":
            orchestrator.reset_history()
            console.print("[green]History cleared.[/green]")
            continue
        if user_input == "/tools":
            print_tools()
            continue

        try:
            start_time = time.time()
            with console.status("[bold cyan]⠋ Thinking...[/bold cyan]", spinner="dots"):
                response = await orchestrator.chat(user_input)
            elapsed = time.time() - start_time

            for call in response.tool_calls:
                _print_tool_call(call["name"], call["args"])

            for tr in response.tool_results:
                _print_tool_result(tr["name"], tr["result"].success, tr["result"].output)

            if response.text:
                console.print()
                try:
                    console.print(Markdown(response.text))
                except Exception:
                    console.print(Panel(response.text, border_style="#00D4FF"))

            console.print(f"[dim]⏱ {elapsed:.1f}s[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Request cancelled.[/yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            console.print("[dim]Check if Ollama is running: ollama serve[/dim]")


def start_chat(model: str | None = None, base_url: str = "http://localhost:11434") -> None:
    async def main() -> None:
        from plasmaagent.agent.tools import TOOL_REGISTRY

        username = _get_username()
        ollama = OllamaClient(base_url=base_url, model=model or "qwen2.5-coder:7b-instruct-q3_k_m")

        if not await _health_check(ollama):
            console.print(f"[bold red]Cannot reach Ollama at {base_url}[/bold red]")
            console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
            return

        models = await ollama.list_models()
        model_names = [m.get("name", "") for m in models]
        if ollama._model not in model_names:
            console.print(f"[yellow]Warning: model '{ollama._model}' not found in Ollama.[/yellow]")
            console.print(f"[dim]Available: {', '.join(model_names)}[/dim]")

        print_banner(ollama._model, base_url, username)
        console.print(f"[dim]Loaded {len(TOOL_REGISTRY)} tools[/dim]")

        orchestrator = AgentOrchestrator(ollama=ollama)
        await _chat_loop(orchestrator, username)

    run_async(main())
