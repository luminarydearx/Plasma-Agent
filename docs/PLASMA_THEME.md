# PlasmaAgent Visual Identity

## Color Palette

PlasmaAgent menggunakan **cosmic plasma** sebagai inspirasi visual — warna-warna yang muncul dari fenomena plasma di alam semesta.

### Core Plasma Colors

| Color Name | Hex Code | Usage | Description |
|------------|----------|-------|-------------|
| **Plasma Cyan** | `#00D4FF` | Primary actions, success | Ionized gas glow - bright cyan seperti plasma di neon tubes |
| **Plasma Magenta** | `#FF00D4` | Errors, warnings, destructive actions | High-energy plasma - vibrant magenta seperti plasma arcs |
| **Plasma Violet** | `#8B00FF` | Information, secondary elements | Deep space plasma - deep violet seperti plasma nebulae |

### Solar/Stellar Colors

| Color Name | Hex Code | Usage | Description |
|------------|----------|-------|-------------|
| **Solar Gold** | `#FFD700` | Highlights, important labels | Solar flares - bright gold seperti solar corona |
| **Solar Orange** | `#FF6B35` | Warnings, attention | Solar prominences - warm orange seperti solar eruptions |

### Nebula Colors

| Color Name | Hex Code | Usage | Description |
|------------|----------|-------|-------------|
| **Nebula Pink** | `#FF1493` | Accents, decorative | Emission nebula - vivid pink seperti Orion Nebula |
| **Nebula Teal** | `#00CED1` | Secondary info | Reflection nebula - cool teal seperti Pleiades |
| **Nebula Purple** | `#9370DB` | Tertiary elements | Planetary nebula - soft purple seperti Ring Nebula |

### Aurora Colors

| Color Name | Hex Code | Usage | Description |
|------------|----------|-------|-------------|
| **Aurora Green** | `#00FF7F` | Success messages | Aurora borealis - bright green seperti northern lights |
| **Aurora Blue** | `#1E90FF` | Info messages | Upper atmosphere aurora - deep blue |

## Usage Guidelines

### Semantic Colors

- **Success**: Aurora Green (`#00FF7F`)
- **Error/Danger**: Plasma Magenta (`#FF00D4`)
- **Warning**: Solar Gold (`#FFD700`)
- **Info**: Plasma Cyan (`#00D4FF`)

### Logo Colors

Logo ASCII art menggunakan kombinasi warna plasma:

```
[#00D4FF]PLASMA[/#00D4FF] - Primary logo text in Plasma Cyan
[#FF00D4]╭─────╮[/#FF00D4] - Box borders in Plasma Magenta
[#FF1493]◉◉◉[/#FF1493] - Energy dots in Nebula Pink
[#FFD700]AGENT[/#FFD700] - Subtitle in Solar Gold
[#00FF7F]v0.1.0[/#00FF7F] - Version in Aurora Green
```

### Terminal Support

PlasmaAgent menggunakan **Rich** library untuk terminal colors dengan **truecolor support** (24-bit).

Warna akan tampil optimal di terminal yang mendukung:
- Windows Terminal
- iTerm2 (macOS)
- GNOME Terminal (Linux)
- VS Code integrated terminal

## Plasma Sphere Concept

Logo "plasma sphere" terinspirasi dari:
- **Tokamak reactors** - donut-shaped plasma containment
- **Solar corona** - plasma atmosphere around the sun
- **Nebulae** - cosmic clouds of ionized gas
- **Aurora** - plasma interactions with Earth's atmosphere

Konsep visual: **Energy contained in a sphere** — merepresentasikan agent yang mengontrol dan mengarahkan energi (tasks) dalam sistem yang terstruktur.

## Implementation

```python
from plasmaagent.cli.theme import console, style_success, style_error, style_warning, style_info

# Using semantic styles
console.print(style_success("Task completed!"))
console.print(style_error("Connection failed"))
console.print(style_warning("Resource limit approaching"))
console.print(style_info("Processing..."))

# Using hex colors directly
console.print("[#00D4FF]Custom message[/#00D4FF]")

# Using panels
from plasmaagent.cli.theme import create_panel
panel = create_panel("Content", title="Title", border_style="plasma_cyan")
console.print(panel)
```

## Accessibility

Warna-warna plasma dipilih dengan mempertimbangkan:
- **Kontras tinggi** terhadap terminal backgrounds gelap
- **Color-blind friendly** untuk critical states (success/error)
- **Vibrant but not harsh** - nyaman untuk extended use

## Inspiration

- **Hermes-Agent** - Minimalist but bold color usage
- **Rich library** - Professional terminal styling
- **NASA imagery** - Real plasma phenomena photography
- **Cyberpunk aesthetics** - High-tech, futuristic feel

## Future Enhancements

- [ ] Animated ASCII logo (optional)
- [ ] Dark/Light theme toggle
- [ ] Custom color schemes per user preference
- [ ] Terminal theme detection and adaptation
