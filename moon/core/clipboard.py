"""System clipboard through the desktop's own tools (many terminals ignore OSC 52)."""

import os
import shutil
import subprocess
import sys


def _copy_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [["pbcopy"]]
    commands = []
    if os.environ.get("WAYLAND_DISPLAY"):
        commands.append(["wl-copy"])
    if os.environ.get("DISPLAY"):
        commands += [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    return commands


def _paste_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [["pbpaste"]]
    commands = []
    if os.environ.get("WAYLAND_DISPLAY"):
        commands.append(["wl-paste", "--no-newline"])
    if os.environ.get("DISPLAY"):
        commands += [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]
    return commands


def copy(text: str) -> bool:
    """Put text on the system clipboard. Returns False when no clipboard tool is available."""
    for command in _copy_commands():
        if shutil.which(command[0]):
            try:
                subprocess.run(command, input=text.encode(), check=True, timeout=2,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except (subprocess.SubprocessError, OSError):
                continue
    return False


def paste() -> str | None:
    """Text on the system clipboard, or None when it can't be read."""
    for command in _paste_commands():
        if shutil.which(command[0]):
            try:
                result = subprocess.run(command, capture_output=True, check=True, timeout=2)
                return result.stdout.decode("utf-8", errors="replace")
            except (subprocess.SubprocessError, OSError):
                continue
    return None
