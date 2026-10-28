"""File and folder icons in the spirit of VS Code's Material Icon Theme.

With a Nerd Font (Moon Code installs "Symbols Nerd Font", which terminals use as a fallback)
every icon is a colored glyph. Without one, emoji are used instead.
"""

from dataclasses import dataclass
from pathlib import Path

from rich.text import Text


@dataclass(frozen=True)
class Icon:
    glyph: str
    color: str


DEFAULT_FILE = Icon("\U000f0214", "#8a93b8")  # 󰈔
FOLDER = Icon("", "#7aa2f7")  #
FOLDER_OPEN = Icon("", "#7aa2f7")  #

EXTENSIONS: dict[str, Icon] = {
    # Languages
    ".py": Icon("", "#ffbc03"), ".pyw": Icon("", "#ffbc03"), ".pyi": Icon("", "#ffbc03"),
    ".ipynb": Icon("", "#f57d01"),
    ".js": Icon("", "#cbcb41"), ".mjs": Icon("", "#cbcb41"), ".cjs": Icon("", "#cbcb41"),
    ".ts": Icon("", "#519aba"), ".mts": Icon("", "#519aba"),
    ".jsx": Icon("", "#20c2e3"), ".tsx": Icon("", "#1d8fcf"),
    ".go": Icon("", "#00add8"), ".rs": Icon("", "#dea584"),
    ".c": Icon("", "#599eff"), ".h": Icon("", "#a074c4"),
    ".cpp": Icon("", "#519aba"), ".cc": Icon("", "#519aba"), ".cxx": Icon("", "#519aba"),
    ".hpp": Icon("", "#a074c4"),
    ".cs": Icon("\U000f031b", "#a074c4"), ".fs": Icon("", "#519aba"),
    ".java": Icon("", "#e76f00"), ".kt": Icon("", "#7f52ff"), ".kts": Icon("", "#7f52ff"),
    ".scala": Icon("", "#cc3e44"), ".swift": Icon("", "#e37933"), ".dart": Icon("", "#36a3f0"),
    ".rb": Icon("", "#e0475a"), ".php": Icon("", "#a074c4"), ".pl": Icon("", "#519aba"),
    ".lua": Icon("", "#51a0cf"), ".r": Icon("\U000f07d4", "#4f8fe0"), ".jl": Icon("", "#a270ba"),
    ".ex": Icon("", "#a074c4"), ".exs": Icon("", "#a074c4"), ".erl": Icon("", "#b83998"),
    ".hs": Icon("", "#a074c4"), ".ml": Icon("", "#e37933"), ".zig": Icon("", "#f69a1b"),
    ".nim": Icon("", "#f3d400"), ".v": Icon("", "#5d87bf"), ".d": Icon("", "#b03931"),
    ".sh": Icon("", "#89e051"), ".bash": Icon("", "#89e051"), ".zsh": Icon("", "#89e051"),
    ".fish": Icon("", "#89e051"), ".ps1": Icon("\U000f0a0a", "#4273ca"),
    ".sql": Icon("", "#dad8d8"), ".graphql": Icon("", "#e535ab"),
    # Web
    ".html": Icon("", "#e44d26"), ".htm": Icon("", "#e44d26"),
    ".css": Icon("", "#42a5f5"), ".scss": Icon("", "#f55385"), ".sass": Icon("", "#f55385"),
    ".vue": Icon("", "#8dc149"), ".svelte": Icon("", "#ff3e00"),
    # Data & config
    ".json": Icon("", "#cbcb41"), ".jsonc": Icon("", "#cbcb41"),
    ".yaml": Icon("", "#ff5370"), ".yml": Icon("", "#ff5370"),
    ".toml": Icon("", "#e07b53"), ".xml": Icon("\U000f05c0", "#e37933"),
    ".ini": Icon("", "#b4bcc8"), ".env": Icon("", "#faf743"), ".lock": Icon("", "#bbbbbb"),
    ".csv": Icon("", "#89e051"),
    # Docs & media
    ".md": Icon("", "#519aba"), ".txt": Icon("\U000f0219", "#89e051"), ".pdf": Icon("", "#e5534b"),
    ".png": Icon("", "#a074c4"), ".jpg": Icon("", "#a074c4"), ".jpeg": Icon("", "#a074c4"),
    ".gif": Icon("", "#a074c4"), ".webp": Icon("", "#a074c4"), ".ico": Icon("", "#cbcb41"),
    ".svg": Icon("\U000f0721", "#ffb13b"), ".mp4": Icon("", "#fd971f"), ".mp3": Icon("", "#ea4c89"),
    ".zip": Icon("", "#eca517"), ".gz": Icon("", "#eca517"), ".tar": Icon("", "#eca517"),
    ".ttf": Icon("", "#ececec"), ".deb": Icon("", "#a80030"),
}

FILENAMES: dict[str, Icon] = {
    "package.json": Icon("", "#e8274b"), "package-lock.json": Icon("", "#7a0d21"),
    "tsconfig.json": Icon("", "#519aba"), "Cargo.toml": Icon("", "#dea584"),
    "Cargo.lock": Icon("", "#dea584"), "go.mod": Icon("", "#00add8"), "go.sum": Icon("", "#00add8"),
    "requirements.txt": Icon("", "#ffbc03"), "pyproject.toml": Icon("", "#ffbc03"),
    "Dockerfile": Icon("\U000f0868", "#458ee6"), "docker-compose.yml": Icon("\U000f0868", "#458ee6"),
    "Makefile": Icon("", "#e37933"), "Justfile": Icon("", "#e37933"),
    ".gitignore": Icon("", "#f54d27"), ".gitattributes": Icon("", "#f54d27"),
    ".gitmodules": Icon("", "#f54d27"), "LICENSE": Icon("", "#d0bf41"),
    "README.md": Icon("\U000f00ba", "#42a5f5"), "CHANGELOG.md": Icon("\uf4a2", "#8bc34a"),
    ".env": Icon("", "#faf743"), ".editorconfig": Icon("", "#fff2f2"),
    "settings.json": Icon("", "#7aa2f7"),
}

FOLDERS: dict[str, Icon] = {
    "src": Icon("", "#4caf50"), "lib": Icon("", "#c0ca33"), "app": Icon("", "#ef5350"),
    "test": Icon("", "#00bfa5"), "tests": Icon("", "#00bfa5"), "spec": Icon("", "#00bfa5"),
    "docs": Icon("", "#448aff"), "doc": Icon("", "#448aff"),
    "scripts": Icon("", "#ffb300"), "bin": Icon("", "#ffb300"),
    "assets": Icon("", "#ffab00"), "images": Icon("", "#ffab00"), "media": Icon("", "#ffab00"),
    "public": Icon("", "#29b6f6"), "static": Icon("", "#29b6f6"),
    "components": Icon("", "#ffca28"), "config": Icon("", "#00bcd4"), "packaging": Icon("", "#8d6e63"),
    "build": Icon("", "#ef5350"), "dist": Icon("", "#ef5350"), "out": Icon("", "#ef5350"),
    ".git": Icon("", "#f54d27"), ".github": Icon("", "#8a93b8"), ".vscode": Icon("", "#2196f3"),
    "node_modules": Icon("", "#8bc34a"), ".venv": Icon("", "#ffbc03"), "venv": Icon("", "#ffbc03"),
}

EMOJI = {
    ".py": "🐍", ".js": "🟨", ".mjs": "🟨", ".ts": "🔷", ".json": "🧾", ".md": "📝",
    ".html": "🌐", ".css": "🎨", ".cs": "🟪", ".sh": "🐚", ".lua": "🌙", ".rs": "🦀",
    ".go": "🐹", ".java": "☕", ".c": "🔧", ".cpp": "🔩", ".rb": "💎", ".php": "🐘",
    ".toml": "⚙️", ".yaml": "⚙️", ".yml": "⚙️", ".txt": "📄", ".sql": "🗄️",
    "folder": "📁", "folder_open": "📂", "default": "📄",
}


def icon(path: Path, expanded: bool = False) -> Icon:
    """The Nerd Font icon and color for a file or folder."""
    if path.is_dir():
        special = FOLDERS.get(path.name.lower()) or FOLDERS.get(path.name)
        if special is None:
            return FOLDER_OPEN if expanded else FOLDER
        glyph = "" if expanded and special.glyph == "" else special.glyph
        return Icon(glyph, special.color)
    return FILENAMES.get(path.name) or EXTENSIONS.get(path.suffix.lower()) or DEFAULT_FILE


def icon_for(path: Path, nerd: bool = False, expanded: bool = False) -> str:
    """Plain icon text (no color)."""
    if nerd:
        return icon(path, expanded).glyph
    if path.is_dir():
        return EMOJI["folder_open" if expanded else "folder"]
    return EMOJI.get(path.suffix.lower(), EMOJI["default"])


def icon_text(path: Path, nerd: bool = False, expanded: bool = False) -> Text:
    """Colored icon, ready to put in a label."""
    if nerd:
        item = icon(path, expanded)
        return Text(item.glyph, style=item.color)
    return Text(icon_for(path, False, expanded))


def icon_markup(path: Path, nerd: bool = False) -> str:
    """Colored icon as Textual markup, for tab labels."""
    if nerd:
        item = icon(path)
        return f"[{item.color}]{item.glyph}[/]"
    return icon_for(path, False)
