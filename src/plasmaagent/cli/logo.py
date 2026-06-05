PLASMA_LOGO_LINES = [
    "[#00D4FF]██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗[/#00D4FF]",
    "[#00D4FF]██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗[/#00D4FF]",
    "[#00D4FF]██████╔╝██║     ███████║███████╗██╔████╔██║███████║[/#00D4FF]",
    "[#00D4FF]██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║[/#00D4FF]",
    "[#00D4FF]██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║[/#00D4FF]",
    "[#00D4FF]╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝[/#00D4FF]",
    "",
    "         [#FF00D4]╭─────╮[/#FF00D4]  [#FFD700]AGENT[/#FFD700]  [#FF00D4]╭─────╮[/#FF00D4]",
    "         [#FF00D4]│[/#FF00D4] [#FF1493]@@@[/#FF1493] [#FF00D4]│[/#FF00D4]  [#00FF7F]v0.1.0[/#00FF7F] [#FF00D4]│[/#FF00D4] [#FF1493]@@@[/#FF1493] [#FF00D4]│[/#FF00D4]",
    "         [#FF00D4]╰─────╯[/#FF00D4]         [#FF00D4]╰─────╯[/#FF00D4]",
]

LOGO_WIDTH = 56


def get_logo() -> str:
    return "\n".join(PLASMA_LOGO_LINES)


def get_logo_centered() -> str:
    import os
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    padding = max(0, (term_width - LOGO_WIDTH) // 2)
    centered = []
    for line in PLASMA_LOGO_LINES:
        if line.strip():
            centered.append(" " * padding + line)
        else:
            centered.append("")
    return "\n".join(centered)
