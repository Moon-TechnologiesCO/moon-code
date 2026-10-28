"""Command line: `moon`, `moon <folder|file>`, `moon new <name>`, `moon update`, `moon --version`."""

import argparse
import os
import shutil
import sys
from pathlib import Path

from moon import __version__
from moon.core import updater
from moon.core.config import Settings
from moon.core.projects import TEMPLATES_BY_ID, create_project

USAGE = """\
moon                      open the welcome screen
moon <folder|file>        open a folder or a file
moon new <name> [-t id]   create a project (templates: {templates})
moon update               install the latest version
moon --version            print the version"""


def _open(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="moon", usage=USAGE.format(templates=", ".join(TEMPLATES_BY_ID)))
    parser.add_argument("--version", action="version", version=f"Moon Code {__version__}")
    parser.add_argument("target", nargs="?", help="folder or file to open")
    options = parser.parse_args(args)

    target = Path(options.target).expanduser().resolve() if options.target else None
    if target is not None and not target.exists():
        if target.suffix:  # Looks like a file name: create it, like `code new.py` does.
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        else:
            print(f"moon: {options.target} doesn't exist.", file=sys.stderr)
            return 1

    from moon.ui.app import MoonCode, UpdateRequest  # Imported late so `moon --version` stays instant.

    result = MoonCode(target).run()
    if isinstance(result, UpdateRequest):
        return _update_and_relaunch(result.reopen)
    return 0


def _update_and_relaunch(reopen: str | None) -> int:
    """Install the update chosen inside the app, then start the new version."""
    code = _update()
    if code != 0:
        print("The update didn't finish. You can try again with: moon update", file=sys.stderr)
        return code
    print("Starting Moon Code…")
    args = [reopen] if reopen else []
    launcher = shutil.which("moon")
    if launcher:
        os.execv(launcher, [launcher, *args])
    os.execv(sys.executable, [sys.executable, "-m", "moon", *args])
    return 0  # Not reached: exec replaces this process.


def _new(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="moon new")
    parser.add_argument("name")
    parser.add_argument("-t", "--template", default="python", choices=sorted(TEMPLATES_BY_ID))
    parser.add_argument("-d", "--dir", default=None, help="parent folder (default: projects_dir setting)")
    parser.add_argument("--no-open", action="store_true", help="create the project without opening it")
    options = parser.parse_args(args)

    parent = Path(options.dir or Settings.load().projects_dir).expanduser()
    try:
        folder = create_project(parent, options.name, options.template)
    except (ValueError, FileExistsError, OSError) as error:
        print(f"moon: {error}", file=sys.stderr)
        return 1
    print(f"Created {folder}")
    return 0 if options.no_open else _open([str(folder)])


def _update() -> int:
    release = updater.newer_release()
    if release is None:
        print(f"Moon Code {__version__} is up to date.")
        return 0
    print(f"Updating Moon Code {__version__} → {release.tag}")
    return updater.install(release)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else None
    if command == "update":
        return _update()
    if command == "new":
        return _new(args[1:])
    return _open(args)
