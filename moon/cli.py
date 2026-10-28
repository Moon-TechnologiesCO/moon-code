"""Línea de comandos: `moon`, `moon update`, `moon --version`."""

import argparse

from moon import __version__
from moon.core import updater


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="moon", description="Moon Code: editor de código para la terminal.")
    parser.add_argument("--version", action="version", version=f"moon {__version__}")
    parser.add_argument("--nerd", action="store_true", help="usar iconos de Nerd Font")
    parser.add_argument("folder", nargs="?", default=".", help="carpeta del proyecto")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("update", help="instalar la última versión publicada")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "update":
        tag = updater.newer_release()
        if tag is None:
            print(f"Moon Code {__version__} ya está al día.")
            return 0
        print(f"Instalando Moon Code {tag}…")
        return updater.install(tag)

    from moon.ui.app import MoonCode

    MoonCode(args.folder, nerd=args.nerd).run()
    return 0
