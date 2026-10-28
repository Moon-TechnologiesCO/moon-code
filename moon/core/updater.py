"""Busca e instala nuevas versiones de Moon Code desde GitHub Releases."""

import json
import subprocess
import sys
import urllib.request

from moon import __version__

REPO = "Moon-TechnologiesCO/moon-code"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' -> (1, 2, 3). Ignora sufijos que no sean números."""
    digits = text.lstrip("v").split("-")[0].split(".")
    return tuple(int(part) for part in digits if part.isdigit())


def latest_release(timeout: float = 3) -> str | None:
    """Etiqueta de la última release, o None si no se puede consultar."""
    try:
        request = urllib.request.Request(LATEST_URL, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)["tag_name"]
    except (OSError, KeyError, ValueError):
        return None


def newer_release() -> str | None:
    """Devuelve la etiqueta de una versión más nueva, o None."""
    tag = latest_release()
    if tag and parse_version(tag) > parse_version(__version__):
        return tag
    return None


def install(tag: str) -> int:
    """Instala la release indicada con pip, usando el mismo Python que ejecuta Moon."""
    source = f"git+https://github.com/{REPO}@{tag}"
    return subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", source])
