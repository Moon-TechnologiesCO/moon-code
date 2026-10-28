"""File icons. Nerd Font glyphs when enabled, emoji otherwise."""

from pathlib import Path

NERD = {
    ".py": "", ".js": "", ".mjs": "", ".ts": "", ".json": "",
    ".md": "", ".html": "", ".css": "", ".cs": "", ".sh": "",
    ".lua": "", ".rs": "", ".go": "", ".java": "", ".c": "",
    ".cpp": "", ".rb": "", ".php": "", ".toml": "", ".yaml": "",
    ".yml": "", ".txt": "", ".sql": "",
    "folder": "", "folder_open": "", "default": "",
}

EMOJI = {
    ".py": "🐍", ".js": "🟨", ".mjs": "🟨", ".ts": "🔷", ".json": "🧾", ".md": "📝",
    ".html": "🌐", ".css": "🎨", ".cs": "🟪", ".sh": "🐚", ".lua": "🌙", ".rs": "🦀",
    ".go": "🐹", ".java": "☕", ".c": "🔧", ".cpp": "🔩", ".rb": "💎", ".php": "🐘",
    ".toml": "⚙️", ".yaml": "⚙️", ".yml": "⚙️", ".txt": "📄", ".sql": "🗄️",
    "folder": "📁", "folder_open": "📂", "default": "📄",
}


def icon_for(path: Path, nerd: bool = False, expanded: bool = False) -> str:
    table = NERD if nerd else EMOJI
    if path.is_dir():
        return table["folder_open" if expanded else "folder"]
    return table.get(path.suffix.lower(), table["default"])
