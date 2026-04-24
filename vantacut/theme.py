from __future__ import annotations

from dataclasses import dataclass

from textual.theme import Theme


@dataclass(frozen=True)
class ThemePalette:
    background: str
    surface: str
    panel: str
    panel_alt: str
    foreground: str
    line: str
    accent: str
    accent_alt: str
    warning: str
    success: str
    danger: str


VANTACUT_DARK = ThemePalette(
    background="#11161f",
    surface="#151d28",
    panel="#1a2431",
    panel_alt="#202d3d",
    foreground="#edf3ff",
    line="#39506c",
    accent="#4aa6ff",
    accent_alt="#93d4ff",
    warning="#ffb347",
    success="#46d28b",
    danger="#ff6b7a",
)


def build_theme() -> Theme:
    palette = VANTACUT_DARK
    return Theme(
        name="vantacut",
        primary=palette.accent,
        secondary=palette.accent_alt,
        warning=palette.warning,
        error=palette.danger,
        success=palette.success,
        accent=palette.accent_alt,
        foreground=palette.foreground,
        background=palette.background,
        surface=palette.surface,
        panel=palette.panel,
        boost=palette.panel_alt,
        dark=True,
        variables={
            "line": palette.line,
            "panel-alt": palette.panel_alt,
            "timeline-video": "#3a7bff",
            "timeline-audio": "#29b27b",
            "timeline-subtitle": "#d7a044",
            "timeline-selected": "#f0f6ff",
            "focus-ring": "#93d4ff",
        },
    )

