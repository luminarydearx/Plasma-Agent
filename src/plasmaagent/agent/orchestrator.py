from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.tools import TOOL_REGISTRY, ToolResult, get_tools_schema


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


def _build_system_prompt(simple: bool = False) -> str:
    home = Path.home()
    user_name = os.getlogin() if hasattr(os, "getlogin") else "user"
    documents = home / "Documents"
    desktop = home / "Desktop"
    downloads = home / "Downloads"
    cwd = Path.cwd()
    
    if simple:
        return f"""You are PlasmaAgent, an intelligent AI assistant.

USER CONTEXT:
- Username: {user_name}
- Home: {home}
- Documents: {documents}
- OS: {"Windows" if os.name == "nt" else "Linux/Mac"}

Respond concisely in the same language the user uses. Be helpful and friendly."""
    
    tool_names = ", ".join(TOOL_REGISTRY.keys())
    
    return f"""You are PlasmaAgent, an intelligent autonomous AI assistant with direct access to the user's computer.

USER CONTEXT:
- Username: {user_name}
- Home directory: {home}
- Documents folder: {documents}
- Desktop folder: {desktop}
- Downloads folder: {downloads}
- Current working directory: {cwd}
- Operating System: {"Windows" if os.name == "nt" else "Linux/Mac"}

AVAILABLE TOOLS ({len(TOOL_REGISTRY)}):
{tool_names}

TOOL CALLING FORMAT:
When you need to use a tool, respond with ONLY a JSON object in this exact format:
{{
  "name": "<tool_name>",
  "arguments": {{
    "<param1>": "<value1>",
    "<param2>": "<value2>"
  }}
}}

GUIDELINES:
1. Use tools when the user asks you to perform actions on their computer.
2. ALWAYS use absolute paths with forward slashes (e.g., {documents}/file.txt).
3. Think step-by-step before acting, but be concise.
4. If a task requires multiple steps, execute them in sequence (one tool call per response).
5. After tool execution, you will receive the result and can decide to call another tool or respond to the user.
6. For file creation: use create_file tool with absolute path and content.
7. For running commands: use execute_shell tool with PowerShell commands.
8. For remembering information: use store_memory tool.
9. For recalling information: use search_memory tool.
10. DANGEROUS commands (rm -rf, format, DROP TABLE) are blocked for safety.

EXAMPLES:
User: "Buat file hello.txt di Documents dengan isi Hello World"
You: {{"name": "create_file", "arguments": {{"path": "{documents}/hello.txt", "content": "Hello World"}}}}

User: "Jalankan perintah Get-Process"
You: {{"name": "execute_shell", "arguments": {{"command": "Get-Process"}}}}

User: "Ingat bahwa warna favorit saya biru"
You: {{"name": "store_memory", "arguments": {{"content": "Warna favorit user adalah biru", "memory_type": "preference"}}}}

Respond in the same language the user uses.
When NOT using a tool, respond with normal text."""


class AgentOrchestrator:
    def __init__(
        self,
        ollama: OllamaClient | None = None,
        system_prompt: str = "",
        max_tool_iterations: int = 5,
        simple_mode: bool = False,
    ):
        self._ollama = ollama or OllamaClient()
        self._simple_mode = simple_mode
        self._system_prompt = system_prompt or _build_system_prompt(simple=simple_mode)
        self._max_iterations = max_tool_iterations
        self._history: list[dict[str, Any]] = []

    def reset_history(self) -> None:
        self._history.clear()

    def set_simple_mode(self, enabled: bool) -> None:
        self._simple_mode = enabled
        self._system_prompt = _build_system_prompt(simple=enabled)

    async def chat(self, user_message: str) -> AgentResponse:
        self._history.append({"role": "user", "content": user_message})

        tool_calls_made: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []
        final_text = ""
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1
            
            try:
                payload = await self._call_model_with_tools()
            except httpx.TimeoutException:
                final_text = "⚠️ Request timeout (90s). Model is thinking too long. Try:\n- `/simple` mode for faster responses\n- Shorter questions\n- Breaking down complex tasks"
                break
            except httpx.HTTPError as e:
                final_text = f"⚠️ Network error: {e}\n\nCheck if Ollama is running: `ollama serve`"
                break
            except Exception as e:
                final_text = f"⚠️ Unexpected error: {e}"
                break

            message = payload.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls") or []

            if not self._simple_mode and not tool_calls and content:
                parsed = _parse_tool_call_from_text(content)
                if parsed:
                    tool_calls = parsed
                    content = ""

            if not tool_calls:
                final_text = content
                self._history.append({"role": "assistant", "content": content})
                break

            if content:
                self._history.append({"role": "assistant", "content": content})

            self._history.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
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

    async def _call_model_with_tools(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._ollama._model,
            "messages": [{"role": "system", "content": self._system_prompt}] + self._history,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.85,
                "repeat_penalty": 1.2,
            },
        }
        
        if not self._simple_mode:
            payload["tools"] = get_tools_schema()

        async with httpx.AsyncClient(timeout=90.0) as client:
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
