"""Checks GitHub Releases for new versions and installs them the same way Moon was installed."""

import json
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from moon import __version__

REPO = "Moon-TechnologiesCO/moon-code"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DEB_PREFIX = "/usr/lib/moon-code"


@dataclass(frozen=True)
class Release:
    tag: str
    deb_url: str | None


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' -> (1, 2, 3). Ignores suffixes like '-beta'."""
    digits = text.strip().lstrip("v").split("-")[0].split(".")
    return tuple(int(part) for part in digits if part.isdigit())


def latest_release(timeout: float = 3) -> Release | None:
    try:
        request = urllib.request.Request(LATEST_URL, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except (OSError, ValueError):
        return None
    tag = data.get("tag_name")
    if not tag:
        return None
    deb = next((a["browser_download_url"] for a in data.get("assets", []) if a.get("name", "").endswith(".deb")), None)
    return Release(tag, deb)


def newer_release() -> Release | None:
    release = latest_release()
    if release and parse_version(release.tag) > parse_version(__version__):
        return release
    return None


def install_method() -> str:
    """'deb' for the Debian package, 'pip' for everything else (pip, macOS installer)."""
    package_dir = Path(__file__).resolve().parents[2]
    return "deb" if str(package_dir).startswith(DEB_PREFIX) else "pip"


def install(release: Release) -> int:
    if install_method() == "deb" and release.deb_url:
        target = Path(tempfile.gettempdir()) / release.deb_url.rsplit("/", 1)[-1]
        print(f"Downloading {target.name}…")
        urllib.request.urlretrieve(release.deb_url, target)
        return subprocess.call(["sudo", "apt-get", "install", "-y", str(target)])
    source = f"git+https://github.com/{REPO}@{release.tag}"
    return subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", source])
