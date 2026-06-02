from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.theme import Theme

PLASMA_COLORS = {
    "plasma_cyan": "#00D4FF",
    "plasma_magenta": "#FF00D4",
    "plasma_violet": "#8B00FF",
    "solar_gold": "#FFD700",
    "solar_orange": "#FF6B35",
    "nebula_pink": "#FF1493",
    "aurora_green": "#00FF7F",
}

plasma_theme = Theme(
    {
        "info": Style(color="cyan"),
        "warning": Style(color="yellow"),
        "danger": Style(color="magenta", bold=True),
        "error": Style(color="magenta", bold=True),
        "success": Style(color="green", bold=True),
        "highlight": Style(bold=True),
        "dim": Style(dim=True),
    }
)

console = Console(theme=plasma_theme, color_system="truecolor")


def style_success(message: str) -> str:
    color = PLASMA_COLORS["aurora_green"].lstrip("#")
    return f"[#{color}]{message}[/#{color}]"


def style_error(message: str) -> str:
    color = PLASMA_COLORS["plasma_magenta"].lstrip("#")
    return f"[bold #{color}]{message}[/bold #{color}]"


def style_warning(message: str) -> str:
    color = PLASMA_COLORS["solar_gold"].lstrip("#")
    return f"[#{color}]{message}[/{color}]"


def style_info(message: str) -> str:
    color = PLASMA_COLORS["plasma_cyan"].lstrip("#")
    return f"[#{color}]{message}[/{color}]"


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
