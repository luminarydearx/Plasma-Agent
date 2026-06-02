"""ASCII logo for PlasmaAgent."""

PLASMA_LOGO = r"""
  ██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗ 
  ██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
  ██████╔╝██║     ███████║███████╗██╔████╔██║███████║
  ██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
  ██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
  ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
  
         ╭─────╮  AGENT  ╭─────╮
         │ ◉◉◉ │  v0.1.0 │ ◉◉◉ │
         ╰─────╯         ╰─────╯
"""

PLASMA_SPHERE = r"""
        ╭─────────╮
       ╱  ◉     ◉  ╲
      │    ╲   ╱    │
      │     ◉      │
      │    ╱   ╲    │
       ╲  ◉     ◉  ╱
        ╰─────────╯
"""


def get_logo(with_sphere: bool = False) -> str:
    """Get the PlasmaAgent logo.

    Args:
        with_sphere: Include plasma sphere

    Returns:
        str: ASCII logo
    """
    if with_sphere:
        return PLASMA_SPHERE + "\n" + PLASMA_LOGO
    return PLASMA_LOGO
