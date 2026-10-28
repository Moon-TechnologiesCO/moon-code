"""Walking, fuzzy matching and searching project files."""

import os
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
                ".mypy_cache", ".pytest_cache", "dist", "build", "target", "bin", "obj"}


def walk_files(root: Path, limit: int = 20_000) -> list[Path]:
    """Project files relative to root, skipping dependency and build folders."""
    found: list[Path] = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not d.startswith("."))
        for name in sorted(files):
            found.append(Path(folder, name).relative_to(root))
            if len(found) >= limit:
                return found
    return found


def fuzzy_score(query: str, candidate: str) -> int | None:
    """Score for a subsequence match (higher is better), or None if no match."""
    if not query:
        return 0
    query, text = query.lower(), candidate.lower()
    score, position, streak = 0, 0, 0
    for char in query:
        index = text.find(char, position)
        if index < 0:
            return None
        streak = streak + 1 if index == position else 0
        score += 1 + streak * 2
        if index == 0 or text[index - 1] in "/_-. ":
            score += 3
        position = index + 1
    name_start = text.rfind("/") + 1
    if query in text[name_start:]:
        score += 10
    return score - len(text) // 20


def fuzzy_filter(query: str, candidates: list[str], limit: int = 50) -> list[str]:
    scored = [(score, c) for c in candidates if (score := fuzzy_score(query, c)) is not None]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, candidate in scored[:limit]]


@dataclass(frozen=True)
class Match:
    path: Path
    line: int
    text: str


def search(root: Path, query: str, limit: int = 500) -> list[Match]:
    """Case-insensitive text search. Uses ripgrep when installed."""
    if not query:
        return []
    matches = list(_search_ripgrep(root, query, limit) if shutil.which("rg") else _search_python(root, query, limit))
    return matches[:limit]


def _search_ripgrep(root: Path, query: str, limit: int) -> Iterator[Match]:
    result = subprocess.run(
        ["rg", "--no-heading", "--line-number", "--color", "never", "--ignore-case",
         "--fixed-strings", "--max-count", "50", query, "."],
        cwd=root, capture_output=True, text=True, check=False,
    )
    for line in result.stdout.splitlines()[:limit]:
        path, number, text = line.split(":", 2)
        yield Match(Path(path.removeprefix("./")), int(number), text.strip())


def _search_python(root: Path, query: str, limit: int) -> Iterator[Match]:
    needle = query.lower()
    count = 0
    for relative in walk_files(root):
        try:
            text = (root / relative).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                yield Match(relative, number, line.strip())
                count += 1
                if count >= limit:
                    return
