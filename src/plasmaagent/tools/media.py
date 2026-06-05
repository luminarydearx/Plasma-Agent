"""Media and screenshot tools for PlasmaAgent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def screenshot(save_path: str = "") -> ToolResult:
    try:
        import pyautogui
        
        if not save_path:
            desktop = Path.home() / "Desktop"
            desktop.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(desktop / f"screenshot_{timestamp}.png")
        
        target = Path(save_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        
        img = pyautogui.screenshot()
        img.save(str(target))
        
        return ToolResult(
            True,
            f"Screenshot saved to {target}",
            {"path": str(target)},
        )
    except ImportError:
        return ToolResult(False, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, f"Screenshot failed: {e}")
