"""Temas de Moon Code: la interfaz (Textual) y el resaltado del editor."""

from rich.style import Style
from textual.theme import Theme
from textual.widgets.text_area import TextAreaTheme

# Tema de interfaz: colores base para toda la app.
MOON_NIGHT = Theme(
    name="moon-night",
    primary="#7aa2f7",
    secondary="#bb9af7",
    accent="#7dcfff",
    warning="#e0af68",
    error="#f7768e",
    success="#9ece6a",
    foreground="#c0caf5",
    background="#1a1b26",
    surface="#1f2335",
    panel="#24283b",
    dark=True,
)

MOON_LIGHT = Theme(
    name="moon-light",
    primary="#2e7de9",
    secondary="#9854f1",
    accent="#007197",
    warning="#8c6c3e",
    error="#f52a65",
    success="#587539",
    foreground="#343b58",
    background="#e1e2e7",
    surface="#d5d6db",
    panel="#c4c8da",
    dark=False,
)

ALL_THEMES = [MOON_NIGHT, MOON_LIGHT]

# Resaltado del editor (colores de tokens) para el tema oscuro.
MOON_EDITOR_NIGHT = TextAreaTheme(
    name="moon-night",
    base_style=Style(color="#c0caf5", bgcolor="#1a1b26"),
    gutter_style=Style(color="#3b4261", bgcolor="#1a1b26"),
    cursor_style=Style(color="#1a1b26", bgcolor="#c0caf5"),
    cursor_line_style=Style(bgcolor="#24283b"),
    selection_style=Style(bgcolor="#33467c"),
    syntax_styles={
        "keyword": Style(color="#bb9af7", bold=True),
        "string": Style(color="#9ece6a"),
        "comment": Style(color="#565f89", italic=True),
        "number": Style(color="#ff9e64"),
        "function": Style(color="#7aa2f7"),
        "type": Style(color="#2ac3de"),
        "operator": Style(color="#89ddff"),
        "variable": Style(color="#c0caf5"),
    },
)

EDITOR_THEMES = {"moon-night": MOON_EDITOR_NIGHT}
