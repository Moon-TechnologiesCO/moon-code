"""Move files to the system trash instead of deleting them, so mistakes can be undone."""

import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote


def trash_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / ".Trash"
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data / "Trash"


def _free_name(folder: Path, name: str) -> str:
    candidate, number = name, 2
    stem, suffix = os.path.splitext(name)
    while (folder / candidate).exists() or (folder.parent / "info" / f"{candidate}.trashinfo").exists():
        candidate = f"{stem} {number}{suffix}"
        number += 1
    return candidate


def move_to_trash(path: Path, trash: Path | None = None) -> Path:
    """Move `path` to the trash and return where it went. Follows the freedesktop.org spec on Linux,
    so the file shows up in the file manager's Trash and can be restored from there."""
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    trash = trash or trash_dir()
    if sys.platform == "darwin" and trash == Path.home() / ".Trash":  # Finder's own Trash
        trash.mkdir(exist_ok=True)
        target = trash / _free_name(trash, path.name)
        shutil.move(str(path), target)
        return target

    files, info = trash / "files", trash / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    name = _free_name(files, path.name)
    (info / f"{name}.trashinfo").write_text(
        "[Trash Info]\n"
        f"Path={quote(str(path))}\n"
        f"DeletionDate={time.strftime('%Y-%m-%dT%H:%M:%S')}\n",
        encoding="utf-8",
    )
    target = files / name
    shutil.move(str(path), target)
    return target
