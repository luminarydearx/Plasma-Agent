"""CLI theme and color configuration for PlasmaAgent."""

from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.theme import Theme

# PlasmaAgent color palette - inspired by cosmic plasma phenomena
# Using Rich-compatible color names and hex values
PLASMA_COLORS = {
    # Core plasma colors
    "plasma_cyan": "#00D4FF",      # Ionized gas glow - primary actions
    "plasma_magenta": "#FF00D4",   # High-energy plasma - errors/warnings
    "plasma_violet": "#8B00FF",    # Deep space plasma - information
    
    # Solar/stellar colors
    "solar_gold": "#FFD700",       # Solar flares and corona
    "solar_orange": "#FF6B35",     # Solar prominences
    
    # Nebula colors
    "nebula_pink": "#FF1493",      # Emission nebula
    
    # Aurora colors
    "aurora_green": "#00FF7F",     # Aurora borealis
}

# Create custom theme with Rich-compatible styles
# Theme values must be Style objects or valid color strings
plasma_theme = Theme(
    {
        # Semantic styles using standard Rich colors
        "info": Style(color="cyan"),
        "warning": Style(color="yellow"),
        "danger": Style(color="magenta", bold=True),
        "error": Style(color="magenta", bold=True),
        "success": Style(color="green", bold=True),
        "highlight": Style(bold=True),
        "dim": Style(dim=True),
    }
)

# Global console instance with truecolor support
console = Console(theme=plasma_theme, color_system="truecolor")


def style_success(message: str) -> str:
    """Style a success message with aurora green.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    return f"[#{PLASMA_COLORS['aurora_green'].lstrip('#')}]{message}[/{PLASMA_COLORS['aurora_green'].lstrip('#')}]"


def style_error(message: str) -> str:
    """Style an error message with plasma magenta.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    color = PLASMA_COLORS['plasma_magenta'].lstrip('#')
    return f"[bold #{color}]{message}[/bold #{color}]"


def style_warning(message: str) -> str:
    """Style a warning message with solar gold.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    color = PLASMA_COLORS['solar_gold'].lstrip('#')
    return f"[#{color}]{message}[/{color}]"


def style_info(message: str) -> str:
    """Style an info message with plasma cyan.

    Args:
        message: Message to style

    Returns:
        str: Styled message
    """
    color = PLASMA_COLORS['plasma_cyan'].lstrip('#')
    return f"[#{color}]{message}[/{color}]"


def pc(color_name: str) -> str:
    """Get hex color code for plasma color name.

    Args:
        color_name: Plasma color name (e.g., 'plasma_cyan', 'solar_gold')

    Returns:
        str: Hex color code (e.g., '#00D4FF')
    """
    return PLASMA_COLORS.get(color_name, "#FFFFFF")


def create_panel(
    content: str,
    title: str = "",
    border_style: str = "plasma_cyan",
    padding: tuple = (1, 2),
) -> Panel:
    """Create a styled panel with plasma colors.

    Args:
        content: Panel content
        title: Panel title
        border_style: Border color name (plasma_cyan, plasma_magenta, solar_gold, etc.)
        padding: Padding as (vertical, horizontal)

    Returns:
        Panel: Styled Rich Panel
    """
    color = pc(border_style)
    return Panel(
        content,
        title=title,
        border_style=color,
        padding=padding,
    )
