"""Small read-only helpers around the git command line."""

import shutil
import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    if not shutil.which("git"):
        return None
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None


def branch(root: Path) -> str | None:
    output = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return output.strip() if output else None


def changes(root: Path) -> list[tuple[str, str]]:
    """(status, path) pairs from `git status --porcelain`."""
    output = _git(root, "status", "--porcelain")
    if not output:
        return []
    return [(line[:2].strip() or "?", line[3:]) for line in output.splitlines() if line]
