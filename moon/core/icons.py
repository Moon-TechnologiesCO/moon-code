"""Iconos para archivos y carpetas. Usa Nerd Font si está disponible; si no, emoji."""

from pathlib import Path

# Glifos de Nerd Font (se ven bien con cualquier Nerd Font instalada).
NERD = {
    ".py": "",
    ".js": "",
    ".ts": "",
    ".json": "",
    ".md": "",
    ".html": "",
    ".css": "",
    ".cs": "",
    ".sh": "",
    ".lua": "",
    ".rs": "",
    ".go": "",
    ".txt": "",
    "folder": "",
    "default": "",
}

# Emoji de respaldo para terminales sin Nerd Font.
EMOJI = {
    ".py": "🐍",
    ".js": "🟨",
    ".ts": "🔷",
    ".json": "🧾",
    ".md": "📝",
    ".html": "🌐",
    ".css": "🎨",
    ".cs": "🟪",
    ".sh": "🐚",
    ".lua": "🌙",
    ".rs": "🦀",
    ".go": "🐹",
    ".txt": "📄",
    "folder": "📁",
    "default": "📄",
}

# Lenguaje (nombre de tree-sitter) según la extensión.
LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".lua": "lua",
    ".rs": "rust",
    ".go": "go",
}


def icon_for(path: Path, nerd: bool = False) -> str:
    table = NERD if nerd else EMOJI
    if path.is_dir():
        return table["folder"]
    return table.get(path.suffix.lower(), table["default"])


def language_for(path: Path) -> str | None:
    return LANGUAGES.get(path.suffix.lower())
