"""Languages: display name, syntax highlighter, comment token and how to run a file or project."""

import shlex
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Language:
    name: str
    syntax: str | None = None
    # Shell command template. Placeholders: {file} {dir} {stem} {out}
    run: str | None = None
    comment: str | None = None


OPEN = "open" if sys.platform == "darwin" else "xdg-open"

PLAIN_TEXT = Language("Plain Text")

_C_LIKE = "//"

LANGUAGES: dict[str, Language] = {
    # Scripting
    ".py": Language("Python", "python", "python3 {file}", "#"),
    ".pyw": Language("Python", "python", "python3 {file}", "#"),
    ".js": Language("JavaScript", "javascript", "node {file}", _C_LIKE),
    ".mjs": Language("JavaScript", "javascript", "node {file}", _C_LIKE),
    ".cjs": Language("JavaScript", "javascript", "node {file}", _C_LIKE),
    ".ts": Language("TypeScript", "javascript", "npx --yes tsx {file}", _C_LIKE),
    ".jsx": Language("JavaScript React", "javascript", None, _C_LIKE),
    ".tsx": Language("TypeScript React", "javascript", None, _C_LIKE),
    ".sh": Language("Shell", "bash", "bash {file}", "#"),
    ".bash": Language("Shell", "bash", "bash {file}", "#"),
    ".zsh": Language("Zsh", "bash", "zsh {file}", "#"),
    ".fish": Language("Fish", None, "fish {file}", "#"),
    ".ps1": Language("PowerShell", None, "pwsh {file}", "#"),
    ".rb": Language("Ruby", None, "ruby {file}", "#"),
    ".php": Language("PHP", None, "php {file}", _C_LIKE),
    ".pl": Language("Perl", None, "perl {file}", "#"),
    ".lua": Language("Lua", None, "lua {file}", "--"),
    ".r": Language("R", None, "Rscript {file}", "#"),
    ".jl": Language("Julia", None, "julia {file}", "#"),
    ".dart": Language("Dart", None, "dart run {file}", _C_LIKE),
    ".ex": Language("Elixir", None, "elixir {file}", "#"),
    ".exs": Language("Elixir", None, "elixir {file}", "#"),
    ".erl": Language("Erlang", None, "escript {file}", "%"),
    ".groovy": Language("Groovy", None, "groovy {file}", _C_LIKE),
    ".tcl": Language("Tcl", None, "tclsh {file}", "#"),
    # Compiled
    ".c": Language("C", None, "gcc {file} -o {out} && {out}", _C_LIKE),
    ".h": Language("C Header", None, None, _C_LIKE),
    ".cpp": Language("C++", None, "g++ -std=c++20 {file} -o {out} && {out}", _C_LIKE),
    ".cc": Language("C++", None, "g++ -std=c++20 {file} -o {out} && {out}", _C_LIKE),
    ".cxx": Language("C++", None, "g++ -std=c++20 {file} -o {out} && {out}", _C_LIKE),
    ".hpp": Language("C++ Header", None, None, _C_LIKE),
    ".cs": Language("C#", None, "cd {dir} && dotnet run", _C_LIKE),
    ".fs": Language("F#", None, "dotnet fsi {file}", _C_LIKE),
    ".java": Language("Java", "java", "java {file}", _C_LIKE),
    ".kt": Language("Kotlin", None, "kotlinc {file} -include-runtime -d {out}.jar && java -jar {out}.jar", _C_LIKE),
    ".kts": Language("Kotlin Script", None, "kotlin {file}", _C_LIKE),
    ".scala": Language("Scala", None, "scala run {file}", _C_LIKE),
    ".go": Language("Go", "go", "go run {file}", _C_LIKE),
    ".rs": Language("Rust", "rust", "rustc {file} -o {out} && {out}", _C_LIKE),
    ".swift": Language("Swift", None, "swift {file}", _C_LIKE),
    ".zig": Language("Zig", None, "zig run {file}", _C_LIKE),
    ".nim": Language("Nim", None, "nim r --hints:off {file}", "#"),
    ".hs": Language("Haskell", None, "runghc {file}", "--"),
    ".ml": Language("OCaml", None, "ocaml {file}", None),
    ".v": Language("V", None, "v run {file}", _C_LIKE),
    ".d": Language("D", None, "rdmd {file}", _C_LIKE),
    ".pas": Language("Pascal", None, "fpc {file} -o{out} && {out}", _C_LIKE),
    ".f90": Language("Fortran", None, "gfortran {file} -o {out} && {out}", "!"),
    ".asm": Language("Assembly", None, None, ";"),
    # Web & data
    ".html": Language("HTML", "html", f"{OPEN} {{file}}"),
    ".htm": Language("HTML", "html", f"{OPEN} {{file}}"),
    ".css": Language("CSS", "css", None),
    ".scss": Language("SCSS", "css", None, _C_LIKE),
    ".vue": Language("Vue", "html", None),
    ".svelte": Language("Svelte", "html", None),
    ".json": Language("JSON", "json", None),
    ".md": Language("Markdown", "markdown", None),
    ".toml": Language("TOML", "toml", None, "#"),
    ".yaml": Language("YAML", "yaml", None, "#"),
    ".yml": Language("YAML", "yaml", None, "#"),
    ".xml": Language("XML", "xml", None),
    ".sql": Language("SQL", "sql", "sqlite3 :memory: < {file}", "--"),
    ".ini": Language("INI", None, None, ";"),
    ".env": Language("Environment", None, None, "#"),
    ".txt": PLAIN_TEXT,
}

FILENAMES: dict[str, Language] = {
    "Makefile": Language("Makefile", None, "cd {dir} && make", "#"),
    "Dockerfile": Language("Dockerfile", None, "cd {dir} && docker build .", "#"),
    "Justfile": Language("Justfile", None, "cd {dir} && just", "#"),
}


def language_for(path: Path) -> Language:
    return FILENAMES.get(path.name) or LANGUAGES.get(path.suffix.lower(), PLAIN_TEXT)


def _format(template: str, path: Path) -> str:
    out = Path(tempfile.gettempdir()) / f"moon-{path.stem}"
    return template.format(
        file=shlex.quote(str(path)),
        dir=shlex.quote(str(path.parent)),
        stem=shlex.quote(path.stem),
        out=shlex.quote(str(out)),
    )


def run_command(path: Path) -> str | None:
    """Shell command that runs the file, or None if the language can't be run."""
    template = language_for(path).run
    return _format(template, path) if template else None


def required_tool(command: str) -> str | None:
    """First program the command needs that isn't installed, if any."""
    for part in command.split("&&"):
        words = shlex.split(part)
        if words and words[0] not in ("cd",) and not words[0].startswith(("/", ".")):
            if shutil.which(words[0]) is None:
                return words[0]
    return None


# Project markers, checked in order. The first one found in the project root wins.
PROJECT_RUNNERS: list[tuple[str, str]] = [
    ("package.json", "npm start"),
    ("Cargo.toml", "cargo run"),
    ("go.mod", "go run ."),
    ("pom.xml", "mvn -q compile exec:java"),
    ("build.gradle", "gradle run"),
    ("build.gradle.kts", "gradle run"),
    ("mix.exs", "mix run"),
    ("pubspec.yaml", "dart run"),
    ("Package.swift", "swift run"),
    ("build.zig", "zig build run"),
    ("Makefile", "make"),
    ("Justfile", "just"),
    ("main.py", "python3 main.py"),
    ("app.py", "python3 app.py"),
    ("manage.py", "python3 manage.py runserver"),
    ("index.html", f"{OPEN} index.html"),
]


def project_command(root: Path) -> str | None:
    """How to run the whole project, based on the files in its root."""
    if any(root.glob("*.csproj")) or any(root.glob("*.fsproj")):
        return "dotnet run"
    for marker, command in PROJECT_RUNNERS:
        if (root / marker).exists():
            return command
    return None
