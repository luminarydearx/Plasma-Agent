"""Clipboard tools for PlasmaAgent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def clipboard_get() -> ToolResult:
    try:
        import pyperclip
        content = pyperclip.paste()
        return ToolResult(True, content, {"content": content})
    except ImportError:
        return ToolResult(False, "pyperclip not installed. Run: pip install pyperclip")
    except Exception as e:
        return ToolResult(False, f"Failed to get clipboard: {e}")


async def clipboard_set(content: str) -> ToolResult:
    try:
        import pyperclip
        pyperclip.copy(content)
        return ToolResult(True, f"Copied {len(content)} chars to clipboard", {"chars": len(content)})
    except ImportError:
        return ToolResult(False, "pyperclip not installed. Run: pip install pyperclip")
    except Exception as e:
        return ToolResult(False, f"Failed to set clipboard: {e}")
