"""Shell and application tools for PlasmaAgent."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def execute_shell(command: str, timeout: int = 300) -> ToolResult:
    dangerous = ["rm -rf /", "format c:", "del /s /q c:\\", "rmdir /s /q c:\\", "DROP DATABASE", "shutdown /s", "shutdown -s"]
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
