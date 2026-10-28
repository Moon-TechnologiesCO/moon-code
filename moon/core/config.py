"""User settings and well-known paths."""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_dir() -> Path:
    """Folder for settings and user extensions (per platform)."""
    override = os.environ.get("MOON_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "moon-code"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "moon-code"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def extensions_dir() -> Path:
    return config_dir() / "extensions"


@dataclass
class Settings:
    theme: str = "moon-night"
    nerd_font: bool = True
    tab_size: int = 4
    show_line_numbers: bool = True
    word_wrap: bool = False
    ai_model: str = "gemma3n:e2b"
    ollama_url: str = "http://localhost:11434"
    projects_dir: str = str(Path.home() / "Projects")
    check_updates: bool = True
    skipped_update: str = ""
    disabled_extensions: list[str] = field(default_factory=list)
    recent_projects: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in known})

    def save(self, path: Path | None = None) -> Path:
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        return path

    def add_recent(self, folder: Path, limit: int = 10) -> None:
        resolved = str(Path(folder).resolve())
        others = [p for p in self.recent_projects if p != resolved]
        self.recent_projects = [resolved, *others][:limit]
