from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.tools import TOOL_REGISTRY, ToolResult
from plasmaagent.agent.permission_manager import (
    request_tool_permission,
    Permission,
    PermissionResult,
)


@dataclass
class AgentResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


def _parse_tool_call_from_text(content: str) -> list[dict[str, Any]]:
    calls = []
    content = content.strip()
    if not content:
        return calls

    try:
        data = json.loads(content)
        if isinstance(data, dict) and "name" in data:
            args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({
                "id": data["name"],
                "function": {"name": data["name"], "arguments": args},
            })
            return calls
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "name" in item:
                    args = item.get("arguments") or item.get("args") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    calls.append({
                        "id": item["name"],
                        "function": {"name": item["name"], "arguments": args},
                    })
            if calls:
                return calls
    except (json.JSONDecodeError, TypeError):
        pass

    json_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```")
    for match in json_pattern.finditer(content):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "name" in data:
                args = data.get("arguments") or data.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                calls.append({
                    "id": data["name"],
                    "function": {"name": data["name"], "arguments": args},
                })
        except (json.JSONDecodeError, TypeError):
            continue

    if not calls:
        brace_pattern = re.compile(r"\{[^{}]*\"name\"\s*:\s*\"[^\"]+\"[^{}]*\}")
        for match in brace_pattern.finditer(content):
            try:
                data = json.loads(match.group(0))
                if "name" in data:
                    args = data.get("arguments") or data.get("args") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    calls.append({
                        "id": data["name"],
                        "function": {"name": data["name"], "arguments": args},
                    })
            except (json.JSONDecodeError, TypeError):
                continue

    return calls


def _get_username() -> str:
    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username:
        return username
    try:
        return os.getlogin()
    except OSError:
        return "user"


def _get_current_datetime_info() -> tuple[str, str]:
    now = datetime.now()
    iso_now = now.isoformat(timespec="seconds")
    readable = now.strftime("%A, %Y-%m-%d %H:%M:%S")
    return iso_now, readable


def _build_system_prompt() -> str:
    home = Path.home()
    user_name = _get_username()
    documents = home / "Documents"
    desktop = home / "Desktop"
    downloads = home / "Downloads"
    iso_now, readable_now = _get_current_datetime_info()

    tool_names = ", ".join(TOOL_REGISTRY.keys())

    return f"""You are PlasmaAgent, an elite AI assistant with direct computer access. You are helpful, precise, and respond in the user's language.

USER: {user_name}
HOME: {home}
DOCUMENTS: {documents}
DESKTOP: {desktop}
OS: {"Windows" if os.name == "nt" else "Linux/Mac"}
CURRENT TIME: {readable_now} (ISO: {iso_now})

AVAILABLE TOOLS ({len(TOOL_REGISTRY)}):
{tool_names}

TOOL CALL FORMAT (respond with ONLY this JSON when using a tool):
{{"name": "<tool_name>", "arguments": {{...}}}}

=== SCHEDULING (CRITICAL - READ CAREFULLY) ===

Use `current_time` tool FIRST if you need to know current time before scheduling.

TWO TYPES OF SCHEDULING:

1. ONE-TIME (specific time, today, tomorrow, once):
   USE: schedule_once
   REQUIRED: ISO datetime "YYYY-MM-DDTHH:MM:SS"

   Examples:
   - "jam 21:18 hari ini" → calculate TODAY's date + 21:18 → "{{"name": "schedule_once", "arguments": {{"task_name": "...", "run_at": "2026-06-05T21:18:00", "commands": [...]}}}}"
   - "besok jam 9 pagi" → tomorrow + 09:00 → "2026-06-06T09:00:00"
   - "10 menit lagi" → current + 10min → ISO format

2. RECURRING (every day, every Monday, hourly):
   USE: cron_schedule
   FORMAT: "minute hour day month weekday" (standard cron)
   - Every day at 21:18 → "18 21 * * *"
   - Every Monday 9am → "0 9 * * 1"
   - Every hour → "0 * * * *"
   - Every 5 minutes → "*/5 * * * *"

DEFAULT: If user does not specify frequency, assume ONE-TIME (today). Only use cron if user says "every", "setiap", "rutin", "recurring".

=== YOUTUBE / WEB SEARCH (CRITICAL FLOW) ===

When user asks to search YouTube or web, ALWAYS follow this flow:

1. Call `youtube_search` or `web_search`
2. PRESENT results as numbered list to user:
   "Berikut hasil pencarian untuk '<query>':
   1. [Title 1] - [brief description]
   2. [Title 2] - [brief description]
   3. [Title 3] - [brief description]
   
   Mana yang ingin Anda buka/subscribe? (sebutkan nomor atau nama)"

3. WAIT for user response. Do NOT auto-open first result.
4. After user picks, perform action (open_app, subscribe, etc)

If result not found, say so and suggest alternatives.

=== KEY TOOLS EXAMPLES ===

File ops:
{{"name": "create_file", "arguments": {{"path": "{documents}/test.txt", "content": "Hello", "overwrite": true}}}}
{{"name": "read_file", "arguments": {{"path": "{documents}/test.txt"}}}}
{{"name": "write_file", "arguments": {{"path": "{documents}/test.txt", "content": "New content", "append": false}}}}

Shell:
{{"name": "execute_shell", "arguments": {{"command": "Get-Process | Select-Object -First 5"}}}}

Apps:
{{"name": "open_app", "arguments": {{"app_name": "msedge", "arguments": "https://youtube.com"}}}}

Search:
{{"name": "web_search", "arguments": {{"query": "Python tutorial", "max_results": 5}}}}
{{"name": "youtube_search", "arguments": {{"query": "Kevin Strong", "max_results": 5}}}}
{{"name": "web_scrape", "arguments": {{"url": "https://example.com", "max_chars": 5000}}}}

Scheduling:
{{"name": "schedule_once", "arguments": {{"task_name": "backup_docs", "run_at": "2026-06-05T21:18:00", "commands": ["echo backup"]}}}}
{{"name": "cron_schedule", "arguments": {{"task_name": "daily_backup", "cron_expression": "0 2 * * *", "commands": ["echo backup"]}}}}

Memory:
{{"name": "store_memory", "arguments": {{"content": "User suka Python", "memory_type": "preference"}}}}
{{"name": "search_memory", "arguments": {{"query": "Python", "limit": 10}}}}

System:
{{"name": "screenshot", "arguments": {{}}}}
{{"name": "clipboard_get", "arguments": {{}}}}
{{"name": "clipboard_set", "arguments": {{"content": "text to copy"}}}}
{{"name": "process_list", "arguments": {{"filter_name": "chrome", "limit": 10}}}}
{{"name": "kill_process", "arguments": {{"name": "notepad"}}}}
{{"name": "send_notification", "arguments": {{"title": "Hello", "message": "Task done", "duration": 5}}}}
{{"name": "system_stats", "arguments": {{}}}}
{{"name": "download_file", "arguments": {{"url": "https://...", "save_path": "{downloads}/file.zip"}}}}
{{"name": "find_file", "arguments": {{"pattern": "*.py", "directory": "{documents}", "max_results": 20}}}}

=== GENERAL RULES ===

- Respond in user's language (Indonesian/English/whatever they use)
- Be concise but complete
- Use tools when user asks for actions on computer
- Use absolute paths with forward slashes
- For dangerous operations, tools will ask for permission
- When NOT using tools, respond normally with helpful text
- For execute_shell, full output will be shown to user
- For open_app, use Windows app names (msedge, chrome, notepad, code, etc) or full paths
- NEVER auto-execute risky actions without user confirmation
- When searching YouTube/web, ALWAYS present list first, ask user to pick
- When scheduling, default to ONE-TIME unless user specifies recurring"""


class AgentOrchestrator:
    def __init__(
        self,
        ollama: OllamaClient | None = None,
        system_prompt: str = "",
        max_tool_iterations: int = 5,
    ):
        self._ollama = ollama or OllamaClient()
        self._system_prompt = system_prompt or _build_system_prompt()
        self._max_iterations = max_tool_iterations
        self._history: list[dict[str, Any]] = []

    def reset_history(self) -> None:
        self._history.clear()

    async def chat(self, user_message: str) -> AgentResponse:
        self._history.append({"role": "user", "content": user_message})

        tool_calls_made: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []
        final_text = ""
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1

            try:
                payload = await self._call_model()
            except httpx.TimeoutException:
                final_text = "⚠️ Request timeout (180s). Try shorter questions or break down complex tasks."
                break
            except httpx.HTTPError as e:
                final_text = f"⚠️ Network error: {e}\n\nCheck if Ollama is running: `ollama serve`"
                break
            except Exception as e:
                final_text = f"⚠️ Unexpected error: {type(e).__name__}: {e}"
                break

            message = payload.get("message", {})
            content = message.get("content", "")

            parsed = _parse_tool_call_from_text(content) if content else []

            if not parsed:
                final_text = content
                self._history.append({"role": "assistant", "content": content})
                break

            self._history.append({
                "role": "assistant",
                "content": content or "",
            })

            for call in parsed:
                fn = call.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", {})
                call_id = call.get("id", name)

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw_args if isinstance(raw_args, dict) else {}

                tool_def = TOOL_REGISTRY.get(name)
                if tool_def is None:
                    result = ToolResult(False, f"Unknown tool: {name}. Available: {list(TOOL_REGISTRY.keys())}")
                else:
                    if tool_def.requires_permission:
                        perm_result = await request_tool_permission(name, args)
                        if not perm_result.allowed:
                            result = ToolResult(False, f"Permission denied: {perm_result.reason}")
                            tool_calls_made.append({"name": name, "args": args, "id": call_id})
                            tool_results.append({"name": name, "result": result})
                            self._history.append({
                                "role": "tool",
                                "content": json.dumps({"success": False, "output": result.output}),
                                "tool_call_id": call_id,
                            })
                            continue

                    try:
                        result = await tool_def.handler(**args)
                    except TypeError as e:
                        result = ToolResult(False, f"Invalid arguments for {name}: {e}")
                    except Exception as e:
                        result = ToolResult(False, f"Tool error: {type(e).__name__}: {e}")

                tool_calls_made.append({"name": name, "args": args, "id": call_id})
                tool_results.append({"name": name, "result": result})

                self._history.append({
                    "role": "tool",
                    "content": json.dumps({
                        "success": result.success,
                        "output": result.output,
                    }),
                    "tool_call_id": call_id,
                })
        else:
            final_text = final_text or "(max tool iterations reached)"

        return AgentResponse(
            text=final_text,
            tool_calls=tool_calls_made,
            tool_results=tool_results,
        )

    async def _call_model(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._ollama._model,
            "messages": [{"role": "system", "content": self._system_prompt}] + self._history,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.85,
                "repeat_penalty": 1.2,
                "num_ctx": 8192,
            },
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self._ollama._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def process_query(self, query: str, user_id: Any = None) -> dict[str, Any]:
        response = await self.chat(query)
        return {
            "response": response.text,
            "tool_calls": response.tool_calls,
            "query": query,
            "model": self._ollama._model,
        }
