from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.orchestrator import AgentOrchestrator
from plasmaagent.agent.config_manager import get_default_model, set_default_model
from plasmaagent.cli.logo import PLASMA_LOGO_LINES, LOGO_WIDTH
from plasmaagent.core.asyncio_compat import run_async


console = Console()


def _get_username() -> str:
    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username:
        return username
    try:
        return os.getlogin()
    except OSError:
        return "user"


def _short_model(model: str) -> str:
    parts = model.split(":")[0].split("-")
    if len(parts) > 3:
        return "-".join(parts[:3])
    return model.split(":")[0]


def _print_tool_call(name: str, args: dict[str, Any]) -> None:
    args_str = ", ".join(f"{k}={_json_truncate(v)}" for k, v in args.items())
    console.print(f"  [magenta]→[/magenta] [bold]{name}[/bold]({args_str})")


def _print_tool_result(name: str, success: bool, output: str, full_output: bool = False) -> None:
    marker = "[green]✓[/green]" if success else "[red]✗[/red]"
    if full_output and output:
        console.print(f"  {marker} [dim]{name}:[/dim]")
        console.print(Panel(output, border_style="dim", title=f"Output: {name}", title_align="left"))
    else:
        preview = output.replace("\n", " ")[:200]
        if len(output) > 200:
            preview += "..."
        console.print(f"  {marker} [dim]{name}:[/dim] {preview}")


def _json_truncate(value: Any, max_len: int = 60) -> str:
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _get_boxed_banner(model: str, ollama_url: str, username: str, tools_count: int) -> str:
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    box_width = min(term_width - 4, 70)
    inner_width = box_width - 4

    logo_lines = []
    for line in PLASMA_LOGO_LINES:
        clean = line.replace("[#00D4FF]", "").replace("[/#00D4FF]", "")
        clean = clean.replace("[#FF00D4]", "").replace("[/#FF00D4]", "")
        clean = clean.replace("[#FFD700]", "").replace("[/#FFD700]", "")
        clean = clean.replace("[#FF1493]", "").replace("[/#FF1493]", "")
        clean = clean.replace("[#00FF7F]", "").replace("[/#00FF7F]", "")
        logo_lines.append(clean)

    logo_display = []
    for line in logo_lines:
        pad = max(0, (inner_width - LOGO_WIDTH) // 2)
        logo_display.append(" " * pad + line)

    separator = "─" * inner_width

    info_lines = [
        f"  [bold #00D4FF]PlasmaAgent Interactive Chat[/bold #00D4FF]",
        f"  [dim]User:[/dim]  [cyan]{username}[/cyan]",
        f"  [dim]Model:[/dim] [cyan]{model}[/cyan]",
        f"  [dim]Ollama:[/dim][cyan]{ollama_url}[/cyan]",
        f"  [dim]Tools:[/dim] [green]{tools_count} loaded[/green]",
        "",
        "  [dim]Commands:[/dim]",
        "    [cyan]exit/quit[/cyan]  - Leave chat",
        "    [cyan]/clear[/cyan]    - Clear screen & chat",
        "    [cyan]/reset[/cyan]    - Clear history only",
        "    [cyan]/tools[/cyan]    - List available tools",
        "    [cyan]/model[/cyan]    - List models (with ctx)",
        "    [cyan]/model <n>[/cyan]- Switch model (saved for next session)",
        "    [cyan]/perms[/cyan]    - View saved permissions",
        "    [cyan]/perms reset[/cyan] - Reset all permissions",
    ]

    all_content = logo_display + [""] + [separator] + [""] + info_lines

    top_border = "╭" + "─" * (box_width - 2) + "╮"
    bot_border = "╰" + "─" * (box_width - 2) + "╯"

    lines = [top_border]
    for content_line in all_content:
        clean_len = len(content_line.replace("[bold #00D4FF]", "").replace("[/bold #00D4FF]", "")
                         .replace("[dim]", "").replace("[/dim]", "")
                         .replace("[cyan]", "").replace("[/cyan]", "")
                         .replace("[green]", "").replace("[/green]", ""))
        pad_right = max(0, inner_width - clean_len)
        lines.append(f"│  {content_line}{' ' * pad_right}│")
    lines.append(bot_border)

    padding = max(0, (term_width - box_width) // 2)
    centered = []
    for line in lines:
        centered.append(" " * padding + line)

    return "\n".join(centered)


def print_banner(model: str, ollama_url: str, username: str, tools_count: int) -> None:
    console.print(_get_boxed_banner(model, ollama_url, username, tools_count))


def print_tools() -> None:
    from plasmaagent.agent.tools import TOOL_REGISTRY
    lines = []
    for name, tool in TOOL_REGISTRY.items():
        perm_marker = "🔒" if tool.requires_permission else "✓"
        lines.append(f"[bold cyan]{name}[/bold cyan] [{perm_marker}]\n  {tool.description}")
    console.print(Panel("\n".join(lines), title=f"Available Tools ({len(TOOL_REGISTRY)})", border_style="#00D4FF"))
    console.print("[dim]🔒 = requires permission, ✓ = no permission needed[/dim]")


async def _list_models(ollama: OllamaClient, current_model: str) -> None:
    try:
        models = await ollama.list_models()
        if not models:
            console.print("[yellow]No models found in Ollama.[/yellow]")
            return
        lines = []
        for m in models:
            name = m.get("name", "unknown")
            size_bytes = m.get("size", 0)
            size_gb = size_bytes / (1024 ** 3) if size_bytes else 0

            ctx_info = ""
            try:
                params = m.get("model_info", {})
                ctx_key = None
                for k in params:
                    if "context_length" in k.lower():
                        ctx_key = k
                        break
                if ctx_key:
                    ctx_info = f" | ctx: {params[ctx_key]:,}"
                else:
                    ctx_info = " | ctx: 8,192 (default)"
            except Exception:
                ctx_info = " | ctx: 8,192"

            marker = " [bold green]← current[/bold green]" if name == current_model else ""
            lines.append(f"[cyan]{name}[/cyan] ({size_gb:.1f} GB{ctx_info}){marker}")
        console.print(Panel("\n".join(lines), title="Available Models", border_style="#00D4FF"))
    except Exception as e:
        console.print(f"[red]Failed to list models: {e}[/red]")


async def _switch_model(ollama: OllamaClient, orchestrator: AgentOrchestrator, new_model: str) -> None:
    try:
        models = await ollama.list_models()
        model_names = [m.get("name", "") for m in models]
        if new_model not in model_names:
            console.print(f"[red]Model '{new_model}' not found.[/red]")
            console.print(f"[dim]Available: {', '.join(model_names)}[/dim]")
            return
        ollama._model = new_model
        orchestrator._ollama._model = new_model
        orchestrator.reset_history()
        set_default_model(new_model)
        console.print(f"[green]Switched to:[/green] [bold cyan]{new_model}[/bold cyan]")
        console.print("[dim]Saved as default for next session. History cleared.[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to switch model: {e}[/red]")


async def _auto_detect_model(ollama: OllamaClient, available_names: list[str]) -> str:
    if not available_names:
        return "unknown"
    preferred = ["qwen2.5-coder", "qwen3", "llama3", "codellama", "mistral", "phi3"]
    for pref in preferred:
        for name in available_names:
            if pref in name.lower():
                return name
    return available_names[0]


async def _health_check(ollama: OllamaClient) -> bool:
    return await ollama.health_check()


async def _chat_loop(orchestrator: AgentOrchestrator, username: str, base_url: str) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.formatted_text import HTML

    session: Any = PromptSession(history=InMemoryHistory())

    while True:
        model = orchestrator._ollama._model
        short = _short_model(model)
        prompt_label = HTML(f"\n<b><style fg='ansicyan'>{username}</style></b><style fg='ansimagenta'>@[{short}]</style></b><style fg='gray'> &gt; </style>")

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
        if user_input == "/clear":
            console.clear()
            from plasmaagent.agent.tools import TOOL_REGISTRY
            print_banner(model, base_url, username, len(TOOL_REGISTRY))
            console.print("[green]Screen cleared. Chat reset.[/green]")
            orchestrator.reset_history()
            continue
        if user_input == "/reset":
            orchestrator.reset_history()
            console.print("[green]History cleared.[/green]")
            continue
        if user_input == "/tools":
            print_tools()
            continue
        if user_input == "/model":
            await _list_models(orchestrator._ollama, model)
            continue
        if user_input.startswith("/model "):
            new_model = user_input[7:].strip()
            if new_model:
                await _switch_model(orchestrator._ollama, orchestrator, new_model)
            else:
                console.print("[yellow]Usage: /model <model_name>[/yellow]")
            continue
        if user_input == "/perms":
            from plasmaagent.agent.permission_manager import list_permissions
            perms = list_permissions()
            if not perms.get("tools"):
                console.print("[dim]No saved permissions yet. Tools will ask for permission on first use.[/dim]")
            else:
                lines = []
                for tool_name, perm in perms.get("tools", {}).items():
                    lines.append(f"  [cyan]{tool_name}[/cyan]: [green]{perm}[/green]")
                console.print(Panel("\n".join(lines), title="Saved Permissions", border_style="yellow"))
            continue
        if user_input == "/perms reset":
            from plasmaagent.agent.permission_manager import reset_permissions
            reset_permissions()
            console.print("[green]All permissions reset. Tools will ask again on next use.[/green]")
            continue

        try:
            start_time = time.time()
            with console.status("[bold cyan]⨋ Thinking...[/bold cyan]", spinner="dots"):
                response = await orchestrator.chat(user_input)
            elapsed = time.time() - start_time

            for call in response.tool_calls:
                _print_tool_call(call["name"], call["args"])

            for tr in response.tool_results:
                is_shell = tr["name"] in ("execute_shell", "open_app")
                _print_tool_result(
                    tr["name"],
                    tr["result"].success,
                    tr["result"].output,
                    full_output=is_shell,
                )

            if response.text:
                console.print()
                try:
                    console.print(Markdown(response.text))
                except Exception:
                    console.print(Panel(response.text, border_style="#00D4FF"))
            else:
                console.print("\n[yellow](no response from model)[/yellow]")

            console.print(f"[dim]⏱ {elapsed:.1f}s | model: {model}[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Request cancelled.[/yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Error ({type(e).__name__}):[/bold red] {e}")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            console.print("[dim]Check if Ollama is running: ollama serve[/dim]")


def start_chat(model: str | None = None, base_url: str = "http://localhost:11434") -> None:
    async def main() -> None:
        from plasmaagent.agent.tools import TOOL_REGISTRY

        username = _get_username()
        ollama = OllamaClient(base_url=base_url, model="placeholder")

        if not await _health_check(ollama):
            console.print(f"[bold red]Cannot reach Ollama at {base_url}[/bold red]")
            console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
            return

        models = await ollama.list_models()
        model_names = [m.get("name", "") for m in models]

        if not model_names:
            console.print("[yellow]No models found in Ollama. Pull a model first: ollama pull qwen2.5-coder:7b[/yellow]")
            return

        selected_model = None

        if model and model in model_names:
            selected_model = model
        else:
            saved_default = get_default_model()
            if saved_default and saved_default in model_names:
                selected_model = saved_default
            else:
                selected_model = await _auto_detect_model(ollama, model_names)
                set_default_model(selected_model)

        ollama._model = selected_model

        print_banner(selected_model, base_url, username, len(TOOL_REGISTRY))

        orchestrator = AgentOrchestrator(ollama=ollama)
        await _chat_loop(orchestrator, username, base_url)

    run_async(main())
