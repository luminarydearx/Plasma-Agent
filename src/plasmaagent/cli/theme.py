import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


_no_color = bool(os.environ.get("NO_COLOR"))
_is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

console = Console(
    force_terminal=_is_tty and not _no_color,
    no_color=_no_color,
    highlight=False,
)


PLASMA_COLORS = {
    "plasma_cyan": "#00D4FF",
    "plasma_magenta": "#FF00D4",
    "plasma_violet": "#8B00FF",
    "solar_gold": "#FFD700",
    "aurora_green": "#00FF7F",
    "nebula_pink": "#FF1493",
    "cosmic_blue": "#0066FF",
    "stellar_white": "#F0F0FF",
    "void_black": "#0A0A0F",
    "deep_space": "#1A1A2E",
}


def style_success(message: str) -> str:
    color = PLASMA_COLORS["aurora_green"]
    return f"[{color}]{message}[/{color}]"


def style_error(message: str) -> str:
    color = PLASMA_COLORS["plasma_magenta"]
    return f"[{color}]{message}[/{color}]"


def style_warning(message: str) -> str:
    color = PLASMA_COLORS["solar_gold"]
    return f"[{color}]{message}[/{color}]"


def style_info(message: str) -> str:
    color = PLASMA_COLORS["plasma_cyan"]
    return f"[{color}]{message}[/{color}]"


def pc(color_name: str) -> str:
    return PLASMA_COLORS.get(color_name, "#FFFFFF")


def create_panel(
    content: str,
    title: str = "",
    border_style: str = "plasma_cyan",
    padding: tuple = (1, 2),
) -> Panel:
    color = pc(border_style)
    return Panel(
        content,
        title=title,
        border_style=color,
        padding=padding,
    )
