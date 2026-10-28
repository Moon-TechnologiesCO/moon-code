"""Moon color themes for the interface, the code editor and the terminal."""

from dataclasses import dataclass

from rich.style import Style
from textual.theme import Theme
from textual.widgets.text_area import TextAreaTheme


@dataclass(frozen=True)
class Palette:
    name: str
    label: str
    dark: bool
    background: str
    surface: str
    panel: str
    foreground: str
    muted: str
    line: str
    selection: str
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    error: str
    # black red green yellow blue magenta cyan white (normal, then bright)
    ansi: tuple[str, ...]


PALETTES = [
    Palette(
        name="moon-night", label="Moon Night", dark=True,
        background="#1a1b26", surface="#16161e", panel="#1f2335", foreground="#c0caf5",
        muted="#565f89", line="#292e42", selection="#33467c",
        primary="#7aa2f7", secondary="#bb9af7", accent="#7dcfff",
        success="#9ece6a", warning="#e0af68", error="#f7768e",
        ansi=("#15161e", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#a9b1d6",
              "#414868", "#ff899d", "#9fe044", "#faba4a", "#8db0ff", "#c7a9ff", "#a4daff", "#c0caf5"),
    ),
    Palette(
        name="moon-midnight", label="Moon Midnight", dark=True,
        background="#0b0c12", surface="#08090d", panel="#12141d", foreground="#d6dcf5",
        muted="#4b5275", line="#1b1e2b", selection="#283457",
        primary="#89b4fa", secondary="#cba6f7", accent="#94e2d5",
        success="#a6e3a1", warning="#f9e2af", error="#f38ba8",
        ansi=("#11111b", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#cba6f7", "#94e2d5", "#bac2de",
              "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#cba6f7", "#94e2d5", "#d6dcf5"),
    ),
    Palette(
        name="moon-light", label="Moon Light", dark=False,
        background="#f5f6fa", surface="#e9ebf2", panel="#dfe2ec", foreground="#343b58",
        muted="#8990b3", line="#e1e3ec", selection="#c7d3f5",
        primary="#2e7de9", secondary="#9854f1", accent="#007197",
        success="#587539", warning="#8c6c3e", error="#f52a65",
        ansi=("#e9e9ed", "#f52a65", "#587539", "#8c6c3e", "#2e7de9", "#9854f1", "#007197", "#6172b0",
              "#a1a6c5", "#f52a65", "#587539", "#8c6c3e", "#2e7de9", "#9854f1", "#007197", "#3760bf"),
    ),
]

PALETTES_BY_NAME = {palette.name: palette for palette in PALETTES}
DEFAULT_THEME = "moon-night"


def palette(name: str) -> Palette:
    return PALETTES_BY_NAME.get(name, PALETTES_BY_NAME[DEFAULT_THEME])


def app_theme(p: Palette) -> Theme:
    return Theme(
        name=p.name, primary=p.primary, secondary=p.secondary, accent=p.accent,
        warning=p.warning, error=p.error, success=p.success, foreground=p.foreground,
        background=p.background, surface=p.surface, panel=p.panel, dark=p.dark,
        variables={"moon-muted": p.muted, "moon-line": p.line},
    )


def editor_theme(p: Palette) -> TextAreaTheme:
    return TextAreaTheme(
        name=p.name,
        base_style=Style(color=p.foreground, bgcolor=p.background),
        gutter_style=Style(color=p.muted, bgcolor=p.background),
        cursor_style=Style(color=p.background, bgcolor=p.foreground),
        cursor_line_style=Style(bgcolor=p.line),
        cursor_line_gutter_style=Style(color=p.foreground, bgcolor=p.line),
        bracket_matching_style=Style(bgcolor=p.selection, bold=True),
        selection_style=Style(bgcolor=p.selection),
        syntax_styles={
            "keyword": Style(color=p.secondary, bold=True),
            "keyword.function": Style(color=p.secondary, bold=True),
            "keyword.return": Style(color=p.secondary, bold=True),
            "keyword.operator": Style(color=p.accent),
            "conditional": Style(color=p.secondary, bold=True),
            "repeat": Style(color=p.secondary, bold=True),
            "include": Style(color=p.secondary),
            "exception": Style(color=p.secondary),
            "string": Style(color=p.success),
            "string.documentation": Style(color=p.success, italic=True),
            "comment": Style(color=p.muted, italic=True),
            "number": Style(color=p.warning),
            "float": Style(color=p.warning),
            "boolean": Style(color=p.warning),
            "function": Style(color=p.primary),
            "function.call": Style(color=p.primary),
            "method": Style(color=p.primary),
            "method.call": Style(color=p.primary),
            "type": Style(color=p.accent),
            "type.builtin": Style(color=p.accent),
            "class": Style(color=p.accent),
            "operator": Style(color=p.accent),
            "punctuation.bracket": Style(color=p.foreground),
            "punctuation.delimiter": Style(color=p.muted),
            "variable": Style(color=p.foreground),
            "variable.parameter": Style(color=p.warning),
            "variable.builtin": Style(color=p.error),
            "constant.builtin": Style(color=p.warning),
            "tag": Style(color=p.error),
            "attribute": Style(color=p.warning),
            "property": Style(color=p.accent),
            "json.label": Style(color=p.primary),
            "toml.type": Style(color=p.secondary),
            "yaml.field": Style(color=p.primary),
            "heading": Style(color=p.primary, bold=True),
            "bold": Style(bold=True),
            "italic": Style(italic=True),
            "link_url": Style(color=p.accent, underline=True),
        },
    )
