from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Permission(str, Enum):
    ALLOW_ALWAYS = "allow_always"
    ALLOW_ONCE = "allow_once"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    permission: Permission
    reason: str = ""


_PERMISSIONS_FILE = Path.home() / ".plasma" / "permissions.json"


def _load_permissions() -> dict[str, Any]:
    if _PERMISSIONS_FILE.exists():
        try:
            return json.loads(_PERMISSIONS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"tools": {}, "paths": {}}
    return {"tools": {}, "paths": {}}


def _save_permissions(data: dict[str, Any]) -> None:
    _PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PERMISSIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_tool_permission(tool_name: str) -> Permission | None:
    data = _load_permissions()
    stored = data.get("tools", {}).get(tool_name)
    if stored:
        return Permission(stored)
    return None


def set_tool_permission(tool_name: str, perm: Permission) -> None:
    data = _load_permissions()
    data.setdefault("tools", {})[tool_name] = perm.value
    _save_permissions(data)


def check_tool_permission(tool_name: str, args: dict[str, Any]) -> PermissionResult:
    stored = get_tool_permission(tool_name)
    if stored == Permission.ALLOW_ALWAYS:
        return PermissionResult(True, Permission.ALLOW_ALWAYS, "Previously allowed always")
    if stored == Permission.DENY:
        return PermissionResult(False, Permission.DENY, "Previously denied")
    return PermissionResult(True, Permission.ALLOW_ONCE, "New request - needs confirmation")


def prompt_permission(tool_name: str, args: dict[str, Any]) -> PermissionResult:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    args_preview = ", ".join(f"{k}={str(v)[:50]}" for k, v in args.items())

    console.print(Panel(
        f"[bold cyan]{tool_name}[/bold cyan]({args_preview})\n\n"
        f"[dim]This tool will execute on your computer.[/dim]",
        title="[yellow]Permission Required[/yellow]",
        border_style="yellow",
    ))

    while True:
        try:
            choice = input("  [A] Allow Once | [W] Allow Always | [D] Deny > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return PermissionResult(False, Permission.DENY, "Cancelled by user")

        if choice in ("a", "allow", "1"):
            return PermissionResult(True, Permission.ALLOW_ONCE, "User allowed once")
        if choice in ("w", "always", "2"):
            set_tool_permission(tool_name, Permission.ALLOW_ALWAYS)
            return PermissionResult(True, Permission.ALLOW_ALWAYS, "User allowed always")
        if choice in ("d", "deny", "3", ""):
            return PermissionResult(False, Permission.DENY, "User denied")
        console.print("  [red]Invalid choice. Use A/W/D.[/red]")


async def request_tool_permission(tool_name: str, args: dict[str, Any]) -> PermissionResult:
    import asyncio
    check = check_tool_permission(tool_name, args)
    if check.permission == Permission.ALLOW_ALWAYS:
        return check
    if check.permission == Permission.DENY:
        return check
    return await asyncio.to_thread(prompt_permission, tool_name, args)


def reset_permissions() -> None:
    if _PERMISSIONS_FILE.exists():
        _PERMISSIONS_FILE.unlink()


def list_permissions() -> dict[str, Any]:
    return _load_permissions()
