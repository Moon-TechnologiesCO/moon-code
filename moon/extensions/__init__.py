"""Extension registry: built-in extensions plus user extensions from the config folder.

A user extension is a single Python file in `<config>/extensions/` that defines:

    NAME = "My Extension"
    DESCRIPTION = "What it does"
    ICON = "✨"               # optional

    def activate(api):
        api.add_command("My Extension: Say hi", "Shows a greeting", lambda: api.notify("Hi!"))
"""

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from moon.core.config import extensions_dir


class ExtensionAPI(Protocol):
    """What an extension can do with the editor."""

    project_root: Path

    def add_command(self, title: str, help: str, callback: Callable[[], Any]) -> None: ...
    def notify(self, message: str, severity: str = "information") -> None: ...
    def run_in_terminal(self, command: str) -> None: ...
    def open_file(self, path: Path, line: int | None = None) -> None: ...
    def active_file(self) -> Path | None: ...
    def save_active(self) -> None: ...
    def reload_file(self, path: Path) -> None: ...


@dataclass(frozen=True)
class Extension:
    id: str
    name: str
    description: str
    icon: str
    activate: Callable[[ExtensionAPI], None] | None = None
    builtin: bool = True


def builtin_extensions() -> list[Extension]:
    from moon.extensions import code_runner, formatter, git_tools, moon_ai

    return [
        Extension("code-runner", "Code Runner", "Run the active file with one click (F5) in the integrated terminal.", "▶", code_runner.activate),
        Extension("formatter", "Formatter", "Format the active file with ruff, black, prettier, gofmt, rustfmt or shfmt.", "✨", formatter.activate),
        Extension("git", "Git", "Branch in the status bar and a Source Control view with changed files.", "⎇", git_tools.activate),
        Extension("moon-ai", "Moon AI", "Chat with local models through Ollama. Your code never leaves your machine.", "🤖", moon_ai.activate),
        Extension("autocomplete", "Autocomplete", "Word and keyword suggestions while you type.", "💡"),
    ]


def user_extensions(folder: Path | None = None) -> tuple[list[Extension], list[str]]:
    """Load extensions from the user folder. Returns (extensions, error messages)."""
    folder = folder or extensions_dir()
    extensions: list[Extension] = []
    errors: list[str] = []
    for file in sorted(folder.glob("*.py")) if folder.is_dir() else []:
        try:
            spec = importlib.util.spec_from_file_location(f"moon_user_ext_{file.stem}", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            extensions.append(Extension(
                id=f"user.{file.stem}",
                name=getattr(module, "NAME", file.stem),
                description=getattr(module, "DESCRIPTION", ""),
                icon=getattr(module, "ICON", "🧩"),
                activate=getattr(module, "activate", None),
                builtin=False,
            ))
        except Exception as error:  # A broken extension must never stop the editor.
            errors.append(f"{file.name}: {error}")
    return extensions, errors


TEMPLATE = '''"""{name}: a Moon Code extension."""

NAME = "{name}"
DESCRIPTION = "Describe what this extension does."
ICON = "✨"


def activate(api):
    def hello():
        path = api.active_file()
        api.notify(f"Hello from {name}! Active file: {{path.name if path else 'none'}}")

    api.add_command("{name}: Hello", "Example command from your extension", hello)
'''


def create_user_extension(name: str, folder: Path | None = None) -> Path:
    folder = folder or extensions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stem = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_") or "extension"
    path = folder / f"{stem}.py"
    if path.exists():
        raise FileExistsError(f"{path} already exists.")
    path.write_text(TEMPLATE.format(name=name), encoding="utf-8")
    return path
