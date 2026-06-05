from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


ToolHandler = Callable[..., Awaitable[ToolResult]]


from plasmaagent.tools import (
    create_file,
    read_file,
    write_file,
    list_directory,
    delete_file,
    file_info,
    find_file,
    execute_shell,
    open_app,
    cron_schedule,
    schedule_once,
    store_memory,
    search_memory,
    system_info,
    current_time,
    system_stats,
    process_list,
    kill_process,
    web_search,
    web_scrape,
    youtube_search,
    download_file,
    clipboard_get,
    clipboard_set,
    screenshot,
    send_notification,
    security_audit,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    requires_permission: bool = True


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "create_file": ToolDefinition(
        name="create_file",
        description="Create a new file at the specified path. Use overwrite=True to replace existing files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to create the file"},
                "content": {"type": "string", "description": "File content", "default": ""},
                "overwrite": {"type": "boolean", "description": "Overwrite if exists", "default": False},
            },
            "required": ["path"],
        },
        handler=create_file,
        requires_permission=True,
    ),
    "read_file": ToolDefinition(
        name="read_file",
        description="Read the content of a file as text. Optionally limit to first N lines.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "max_lines": {"type": "integer", "description": "Max lines to read (optional)"},
            },
            "required": ["path"],
        },
        handler=read_file,
        requires_permission=False,
    ),
    "write_file": ToolDefinition(
        name="write_file",
        description="Write content to a file. Use append=True to add to existing content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write"},
                "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
            },
            "required": ["path", "content"],
        },
        handler=write_file,
        requires_permission=True,
    ),
    "list_directory": ToolDefinition(
        name="list_directory",
        description="List files and directories at the specified path. Use recursive=True for nested listing.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "recursive": {"type": "boolean", "description": "List recursively", "default": False},
            },
        },
        handler=list_directory,
        requires_permission=False,
    ),
    "delete_file": ToolDefinition(
        name="delete_file",
        description="Delete a file or directory. Use recursive=True for directories.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "recursive": {"type": "boolean", "description": "Required for directories", "default": False},
            },
            "required": ["path"],
        },
        handler=delete_file,
        requires_permission=True,
    ),
    "file_info": ToolDefinition(
        name="file_info",
        description="Get detailed information about a file or directory (size, dates, permissions).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to inspect"},
            },
            "required": ["path"],
        },
        handler=file_info,
        requires_permission=False,
    ),
    "find_file": ToolDefinition(
        name="find_file",
        description="Find files matching a pattern (e.g., '*.txt', 'report*.pdf') in a directory.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "File pattern to search for (e.g., '*.txt', 'report*.pdf')"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "max_results": {"type": "integer", "description": "Maximum number of results", "default": 20},
            },
            "required": ["pattern"],
        },
        handler=find_file,
        requires_permission=False,
    ),
    "execute_shell": ToolDefinition(
        name="execute_shell",
        description="Execute a shell command (PowerShell on Windows, bash on Linux/Mac). Use for system tasks.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 300},
            },
            "required": ["command"],
        },
        handler=execute_shell,
        requires_permission=True,
    ),
    "open_app": ToolDefinition(
        name="open_app",
        description="Open an application, URL, or file with its default program.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name, URL, or file path"},
                "arguments": {"type": "string", "description": "Additional arguments (optional)", "default": ""},
            },
            "required": ["app_name"],
        },
        handler=open_app,
        requires_permission=True,
    ),
    "cron_schedule": ToolDefinition(
        name="cron_schedule",
        description="Schedule a recurring task using cron expression (e.g., '0 9 * * *' for daily at 9am).",
        parameters={
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Name for the scheduled task"},
                "cron_expression": {"type": "string", "description": "Cron expression (minute hour day month weekday)"},
                "commands": {"type": "array", "items": {"type": "string"}, "description": "List of commands to execute"},
            },
            "required": ["task_name", "cron_expression", "commands"],
        },
        handler=cron_schedule,
        requires_permission=True,
    ),
    "schedule_once": ToolDefinition(
        name="schedule_once",
        description="Schedule a one-time task at a specific datetime (ISO format: YYYY-MM-DDTHH:MM:SS).",
        parameters={
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Name for the task"},
                "run_at": {"type": "string", "description": "ISO datetime to run the task"},
                "commands": {"type": "array", "items": {"type": "string"}, "description": "List of commands to execute"},
            },
            "required": ["task_name", "run_at", "commands"],
        },
        handler=schedule_once,
        requires_permission=True,
    ),
    "store_memory": ToolDefinition(
        name="store_memory",
        description="Store information in long-term memory for future recall.",
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
        requires_permission=False,
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
        requires_permission=False,
    ),
    "system_info": ToolDefinition(
        name="system_info",
        description="Get system information (OS, Python, hostname, user, cwd).",
        parameters={"type": "object", "properties": {}},
        handler=system_info,
        requires_permission=False,
    ),
    "current_time": ToolDefinition(
        name="current_time",
        description="Get current date and time.",
        parameters={"type": "object", "properties": {}},
        handler=current_time,
        requires_permission=False,
    ),
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the web using DuckDuckGo. Returns titles and URLs. Use when user asks to search for something online.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return", "default": 5},
            },
            "required": ["query"],
        },
        handler=web_search,
        requires_permission=False,
    ),
    "youtube_search": ToolDefinition(
        name="youtube_search",
        description="Search YouTube for videos. Returns numbered list with titles and URLs. ALWAYS use this tool when user asks to search YouTube, find videos, or look for channels. Present results to user and ask which one to open BEFORE using open_app.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return", "default": 5},
            },
            "required": ["query"],
        },
        handler=youtube_search,
        requires_permission=False,
    ),
    "screenshot": ToolDefinition(
        name="screenshot",
        description="Take a screenshot of the current screen and save it as PNG.",
        parameters={
            "type": "object",
            "properties": {
                "save_path": {"type": "string", "description": "Path to save screenshot (default: Desktop/screenshot_TIMESTAMP.png)"},
            },
        },
        handler=screenshot,
        requires_permission=True,
    ),
    "clipboard_get": ToolDefinition(
        name="clipboard_get",
        description="Get the current text content from the system clipboard.",
        parameters={"type": "object", "properties": {}},
        handler=clipboard_get,
        requires_permission=False,
    ),
    "clipboard_set": ToolDefinition(
        name="clipboard_set",
        description="Set text content to the system clipboard.",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text to copy to clipboard"},
            },
            "required": ["content"],
        },
        handler=clipboard_set,
        requires_permission=False,
    ),
    "process_list": ToolDefinition(
        name="process_list",
        description="List running processes sorted by memory usage. Can filter by name.",
        parameters={
            "type": "object",
            "properties": {
                "filter_name": {"type": "string", "description": "Filter processes by name (optional)", "default": ""},
                "limit": {"type": "integer", "description": "Max processes to show", "default": 20},
            },
        },
        handler=process_list,
        requires_permission=False,
    ),
    "kill_process": ToolDefinition(
        name="kill_process",
        description="Kill/terminate a running process by name or PID.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Process name to kill", "default": ""},
                "pid": {"type": "integer", "description": "Process ID to kill", "default": 0},
            },
        },
        handler=kill_process,
        requires_permission=True,
    ),
    "send_notification": ToolDefinition(
        name="send_notification",
        description="Send a desktop notification with title and message. Duration in seconds (default: 5).",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification message"},
                "duration": {"type": "integer", "description": "Display duration in seconds", "default": 5},
            },
            "required": ["title", "message"],
        },
        handler=send_notification,
        requires_permission=True,
    ),
    "system_stats": ToolDefinition(
        name="system_stats",
        description="Get current system statistics: CPU usage, memory usage, disk usage.",
        parameters={"type": "object", "properties": {}},
        handler=system_stats,
        requires_permission=False,
    ),
    "download_file": ToolDefinition(
        name="download_file",
        description="Download a file from URL. Saves to Downloads folder by default, or specify save_path.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to download from"},
                "save_path": {"type": "string", "description": "Path to save file (optional, defaults to Downloads folder)"},
            },
            "required": ["url"],
        },
        handler=download_file,
        requires_permission=True,
    ),
    "web_scrape": ToolDefinition(
        name="web_scrape",
        description="Scrape and extract text content from a web page. Removes HTML tags, scripts, and styles. Useful for reading articles or documentation.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "max_chars": {"type": "integer", "description": "Maximum characters to return", "default": 10000},
            },
            "required": ["url"],
        },
        handler=web_scrape,
        requires_permission=False,
    ),
    "security_audit": ToolDefinition(
        name="security_audit",
        description="Perform comprehensive security audit on a project. Detects SQL injection, XSS, path traversal, hardcoded secrets, command injection, insecure crypto, and debug mode vulnerabilities. Returns security score and detailed report. 100% offline, no data sent externally.",
        parameters={
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to project directory to audit"},
                "file_extensions": {"type": "array", "items": {"type": "string"}, "description": "File extensions to scan (default: .py, .js, .ts, .jsx, .tsx, .go, .rs, .php, .rb)"},
            },
            "required": ["project_path"],
        },
        handler=security_audit,
        requires_permission=False,
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
