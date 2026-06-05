from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.tools import TOOL_REGISTRY, ToolResult


@dataclass
class AgentResponse:
    text: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]


def _parse_tool_call_from_text(content: str) -> list[dict[str, Any]]:
    calls = []
    content = content.strip()

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
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "user"


def _build_system_prompt() -> str:
    home = Path.home()
    user_name = _get_username()
    documents = home / "Documents"
    desktop = home / "Desktop"
    downloads = home / "Downloads"
    cwd = Path.cwd()

    tool_names = ", ".join(TOOL_REGISTRY.keys())

    return f"""You are PlasmaAgent, an AI assistant with direct computer access.

USER: {user_name}
HOME: {home}
DOCUMENTS: {documents}
DESKTOP: {desktop}
OS: {"Windows" if os.name == "nt" else "Linux/Mac"}

TOOLS: {tool_names}

TOOL CALL FORMAT (respond with ONLY this JSON when using a tool):
{{"name": "<tool_name>", "arguments": {{...}}}}

EXAMPLES:
- Create file: {{"name": "create_file", "arguments": {{"path": "{documents}/test.txt", "content": "Hello"}}}}
- Run command: {{"name": "execute_shell", "arguments": {{"command": "Get-Process"}}}}
- Remember: {{"name": "store_memory", "arguments": {{"content": "User likes Python", "memory_type": "preference"}}}}

RULES:
- Use tools when user asks for actions on computer
- Use absolute paths with forward slashes
- Be concise, no unnecessary explanation
- Respond in user's language
- When NOT using tools, respond normally"""


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
                final_text = "⚠️ Request timeout (120s). Try shorter questions or break down complex tasks."
                break
            except httpx.HTTPError as e:
                final_text = f"⚠️ Network error: {e}\n\nCheck if Ollama is running: `ollama serve`"
                break
            except Exception as e:
                final_text = f"⚠️ Unexpected error: {e}"
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
                    try:
                        result = await tool_def.handler(**args)
                    except TypeError as e:
                        result = ToolResult(False, f"Invalid arguments for {name}: {e}")
                    except Exception as e:
                        result = ToolResult(False, f"Tool error: {e}")

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
                "num_ctx": 2048,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
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
