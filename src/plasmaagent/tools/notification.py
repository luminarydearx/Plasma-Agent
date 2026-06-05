"""Notification tools for PlasmaAgent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def send_notification(title: str, message: str, duration: int = 5) -> ToolResult:
    try:
        import plyer
        
        plyer.notification.notify(
            title=title,
            message=message,
            timeout=duration,
        )
        
        return ToolResult(
            True,
            f"Notification sent: {title}",
            {"title": title, "message": message, "duration": duration},
        )
    except ImportError:
        return ToolResult(False, "plyer not installed. Run: pip install plyer")
    except Exception as e:
        return ToolResult(False, f"Notification failed: {e}")
