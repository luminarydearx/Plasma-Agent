from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


ToolHandler = Callable[..., Awaitable[ToolResult]]

DANGEROUS_DIRS = {
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
}


def _is_safe(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    for dangerous in DANGEROUS_DIRS:
        try:
            resolved.relative_to(dangerous)
            return False
        except ValueError:
            continue
    return True


async def create_file(path: str, content: str = "", overwrite: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target} is in system directory")
    if target.exists() and not overwrite:
        return ToolResult(False, f"File already exists: {target}. Use overwrite=True to replace.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult(True, f"Created file: {target} ({len(content)} chars)", {"path": str(target)})


async def read_file(path: str, max_lines: int | None = None) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"File not found: {target}")
    if not target.is_file():
        return ToolResult(False, f"Not a file: {target}")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolResult(False, "Binary file, cannot read as text")
    if max_lines:
        content = "\n".join(content.split("\n")[:max_lines])
    return ToolResult(True, content, {"path": str(target), "chars": len(content)})


async def write_file(path: str, content: str, append: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8") as f:
        f.write(content)
    action = "Appended" if append else "Wrote"
    return ToolResult(True, f"{action} {len(content)} chars to {target}", {"path": str(target)})


async def list_directory(path: str = ".", recursive: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"Directory not found: {target}")
    if not target.is_dir():
        return ToolResult(False, f"Not a directory: {target}")
    items = sorted(target.rglob("*") if recursive else target.iterdir())
    entries = []
    for item in items:
        if item.name.startswith("."):
            continue
        entry_type = "DIR" if item.is_dir() else "FILE"
        try:
            size = item.stat().st_size if item.is_file() else 0
        except OSError:
            size = 0
        entries.append({
            "type": entry_type,
            "name": str(item.relative_to(target)),
            "size": size,
        })
    return ToolResult(True, f"Listed {len(entries)} items in {target}", {"items": entries})


async def delete_file(path: str, recursive: bool = False) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not _is_safe(target):
        return ToolResult(False, f"Access denied: {target}")
    if not target.exists():
        return ToolResult(False, f"Not found: {target}")
    if target.is_dir():
        if not recursive:
            return ToolResult(False, "Use recursive=True to delete directories")
        import shutil
        shutil.rmtree(target)
    else:
        target.unlink()
    return ToolResult(True, f"Deleted: {target}", {"path": str(target)})


async def file_info(path: str) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return ToolResult(False, f"Not found: {target}")
    stat = target.stat()
    info = {
        "path": str(target),
        "type": "directory" if target.is_dir() else "file",
        "size_bytes": stat.st_size,
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "permissions": oct(stat.st_mode)[-3:],
    }
    return ToolResult(True, json.dumps(info, indent=2), info)


async def execute_shell(command: str, timeout: int = 300) -> ToolResult:
    dangerous = ["rm -rf /", "format c:", "del /s /q c:\\", "rmdir /s /q c:\\", "DROP DATABASE", "shutdown /s"]
    for pattern in dangerous:
        if pattern.lower() in command.lower():
            return ToolResult(False, f"Dangerous command blocked: {pattern}")
    shell_name = "powershell" if sys.platform == "win32" else "bash"
    shell_flag = "-Command" if sys.platform == "win32" else "-c"
    try:
        result = subprocess.run(
            [shell_name, shell_flag, command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        if not output.strip():
            output = f"Exit code: {result.returncode}"
        return ToolResult(
            result.returncode == 0,
            output.strip(),
            {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(False, f"Execution failed: {e}")


async def open_app(app_name: str, arguments: str = "") -> ToolResult:
    try:
        if sys.platform == "win32":
            cmd = f"Start-Process '{app_name}'"
            if arguments:
                cmd += f" -ArgumentList '{arguments}'"
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return ToolResult(True, f"Opened: {app_name} {arguments}".strip())
            return ToolResult(False, f"Failed to open {app_name}: {result.stderr}")
        else:
            cmd = ["xdg-open", app_name] if "://" in app_name or "/" in app_name else [app_name]
            if arguments:
                cmd.extend(arguments.split())
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ToolResult(True, f"Opened: {app_name} {arguments}".strip())
    except FileNotFoundError:
        return ToolResult(False, f"Application not found: {app_name}")
    except Exception as e:
        return ToolResult(False, f"Failed to open app: {e}")


async def cron_schedule(task_name: str, cron_expression: str, commands: list[str]) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.scheduling.service import SchedulingService

        db = get_database()
        await db.connect()
        try:
            task_id = uuid4()
            payload = json.dumps({"commands": commands})
            async with db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO tasks (id, name, status, payload, created_at, updated_at) "
                        "VALUES (%s, %s, 'PENDING', %s, NOW(), NOW())",
                        (task_id, task_name, payload),
                    )
            service = SchedulingService(db)
            result = await service.enable_schedule(
                task_id=task_id,
                cron_expression=cron_expression,
            )
            if result is None:
                return ToolResult(False, f"Failed to schedule task '{task_name}'")
            next_run = result.next_run_at
            return ToolResult(
                True,
                f"Scheduled '{task_name}' with cron '{cron_expression}'. Next run: {next_run}",
                {"task_id": str(task_id), "next_run": str(next_run)},
            )
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to schedule: {e}")


async def store_memory(content: str, memory_type: str = "fact", metadata: dict[str, Any] | None = None) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService
        from plasmaagent.memory.models import MemoryType

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                mt = MemoryType(memory_type)
                memory = await service.store_memory(content, mt, metadata=metadata or {})
                await conn.commit()
                return ToolResult(True, f"Stored memory: {memory.id}", {"id": str(memory.id)})
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to store memory: {e}")


async def search_memory(query: str, limit: int = 10) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()
        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                memories = await service.search_memories(query, limit=limit)
                if not memories:
                    return ToolResult(True, "No memories found", {"results": []})
                results = [
                    {"id": str(m.id), "type": m.memory_type.value, "content": m.content}
                    for m in memories
                ]
                formatted = "\n".join(f"[{r['id']}] ({r['type']}) {r['content']}" for r in results)
                return ToolResult(True, formatted, {"results": results})
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Search failed: {e}")


async def system_info() -> ToolResult:
    import platform
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "user": os.getlogin() if hasattr(os, "getlogin") else "unknown",
        "cwd": str(Path.cwd()),
        "home": str(Path.home()),
    }
    return ToolResult(True, json.dumps(info, indent=2), info)


async def current_time() -> ToolResult:
    now = datetime.now()
    return ToolResult(True, now.isoformat(), {"timestamp": now.isoformat()})


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "create_file": ToolDefinition(
        name="create_file",
        description="Create a new file at the specified path with optional content. Will not overwrite existing files unless overwrite=True.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "File content", "default": ""},
                "overwrite": {"type": "boolean", "description": "Overwrite if exists", "default": False},
            },
            "required": ["path"],
        },
        handler=create_file,
    ),
    "read_file": ToolDefinition(
        name="read_file",
        description="Read text content from a file. Supports limiting output lines.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "max_lines": {"type": "integer", "description": "Max lines to return"},
            },
            "required": ["path"],
        },
        handler=read_file,
    ),
    "write_file": ToolDefinition(
        name="write_file",
        description="Write content to a file. Use append=True to append instead of overwrite.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "Content to write"},
                "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
            },
            "required": ["path", "content"],
        },
        handler=write_file,
    ),
    "list_directory": ToolDefinition(
        name="list_directory",
        description="List files and directories at the specified path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "recursive": {"type": "boolean", "description": "List recursively", "default": False},
            },
        },
        handler=list_directory,
    ),
    "delete_file": ToolDefinition(
        name="delete_file",
        description="Delete a file or directory. Use recursive=True for directories.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "recursive": {"type": "boolean", "description": "Delete directory recursively", "default": False},
            },
            "required": ["path"],
        },
        handler=delete_file,
    ),
    "file_info": ToolDefinition(
        name="file_info",
        description="Get metadata about a file or directory (size, dates, permissions).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory path"},
            },
            "required": ["path"],
        },
        handler=file_info,
    ),
    "execute_shell": ToolDefinition(
        name="execute_shell",
        description="Execute a shell command (PowerShell on Windows, bash on Linux). Dangerous commands are blocked. Returns full stdout/stderr output.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
            },
            "required": ["command"],
        },
        handler=execute_shell,
    ),
    "open_app": ToolDefinition(
        name="open_app",
        description="Open an application or URL. Examples: 'msedge', 'chrome', 'notepad', 'https://youtube.com', 'C:\\Program Files\\app.exe'. On Windows uses Start-Process.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name, path, or URL to open"},
                "arguments": {"type": "string", "description": "Optional arguments (e.g., URL to open in browser, search query)", "default": ""},
            },
            "required": ["app_name"],
        },
        handler=open_app,
    ),
    "cron_schedule": ToolDefinition(
        name="cron_schedule",
        description="Schedule a recurring task using cron expression. Format: 'minute hour day month weekday'. Examples: '0 * * * *' (every hour), '0 9 * * 1' (every Monday 9am), '30 8 * * *' (daily 8:30am).",
        parameters={
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Name for the scheduled task"},
                "cron_expression": {"type": "string", "description": "Cron expression (5 fields: min hour day month weekday)"},
                "commands": {"type": "array", "items": {"type": "string"}, "description": "List of shell commands to execute"},
            },
            "required": ["task_name", "cron_expression", "commands"],
        },
        handler=cron_schedule,
    ),
    "store_memory": ToolDefinition(
        name="store_memory",
        description="Store information in long-term memory for future recall. Types: fact, preference, task, decision, error.",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content"},
                "memory_type": {"type": "string", "description": "Memory type", "default": "fact"},
                "metadata": {"type": "object", "description": "Optional metadata"},
            },
            "required": ["content"],
        },
        handler=store_memory,
    ),
    "search_memory": ToolDefinition(
        name="search_memory",
        description="Search long-term memory for relevant information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
        handler=search_memory,
    ),
    "system_info": ToolDefinition(
        name="system_info",
        description="Get system information (OS, Python, hostname, user, cwd).",
        parameters={"type": "object", "properties": {}},
        handler=system_info,
    ),
    "current_time": ToolDefinition(
        name="current_time",
        description="Get current date and time.",
        parameters={"type": "object", "properties": {}},
        handler=current_time,
    ),
}


def get_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOL_REGISTRY.values()
    ]
