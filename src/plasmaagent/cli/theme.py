"""CLI theme and color configuration."""

from rich.console import Console
from rich.theme import Theme

# PlasmaAgent color palette
PLASMA_COLORS = {
    "cyan": "#00FFFF",  # Electric Cyan - primary actions
    "magenta": "#FF00FF",  # Plasma Magenta - errors/warnings
    "violet": "#8B00FF",  # Deep Violet - information
    "white": "#FFFFFF",  # Plasma Core - highlights
    "dark": "#1A1A2E",  # Dark Matter - backgrounds
}

# Create custom theme
plasma_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold magenta",
        "error": "bold magenta",
        "success": "bold cyan",
        "highlight": "bold white",
        "dim": "dim white",
    }
)

# Global console instance
console = Console(theme=plasma_theme)


def style_success(message: str) -> str:
    """Style a success message.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    return f"[cyan]{message}[/cyan]"


def style_error(message: str) -> str:
    """Style an error message.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    return f"[bold magenta]{message}[/bold magenta]"


def style_warning(message: str) -> str:
    """Style a warning message.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    return f"[yellow]{message}[/yellow]"


def style_info(message: str) -> str:
    """Style an info message.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    return f"[violet]{message}[/violet]"
