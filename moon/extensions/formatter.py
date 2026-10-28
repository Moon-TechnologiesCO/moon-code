"""Formatter: formats the active file with the first matching tool that is installed."""

import shutil
import subprocess
from pathlib import Path

FORMATTERS: dict[str, list[list[str]]] = {
    ".py": [["ruff", "format"], ["black", "-q"]],
    ".js": [["prettier", "--write"]],
    ".ts": [["prettier", "--write"]],
    ".css": [["prettier", "--write"]],
    ".html": [["prettier", "--write"]],
    ".json": [["prettier", "--write"]],
    ".md": [["prettier", "--write"]],
    ".go": [["gofmt", "-w"]],
    ".rs": [["rustfmt"]],
    ".sh": [["shfmt", "-w"]],
    ".lua": [["stylua"]],
}


def formatter_for(path: Path) -> list[str] | None:
    for command in FORMATTERS.get(path.suffix.lower(), []):
        if shutil.which(command[0]):
            return command
    return None


def format_active(api) -> None:
    path = api.active_file()
    if path is None:
        api.notify("Open a file to format it.", "warning")
        return
    command = formatter_for(path)
    if command is None:
        tools = ", ".join(c[0] for c in FORMATTERS.get(path.suffix.lower(), [])) or "none known"
        api.notify(f"No formatter installed for {path.suffix or 'this file'} (tries: {tools}).", "warning")
        return
    api.save_active()
    result = subprocess.run([*command, str(path)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        api.notify(f"{command[0]} failed: {(result.stderr or result.stdout).strip()[:200]}", "error")
        return
    api.reload_file(path)
    api.notify(f"Formatted with {command[0]}.")


def activate(api) -> None:
    api.add_command("Format Document", "Format the active file", lambda: format_active(api))
