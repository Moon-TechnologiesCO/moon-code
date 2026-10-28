"""Project templates for "New Project"."""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    files: dict[str, str]
    main: str | None = None


TEMPLATES = [
    Template("empty", "Empty", {"README.md": "# {name}\n"}, "README.md"),
    Template(
        "python",
        "Python",
        {
            "main.py": 'def main() -> None:\n    print("Hello from {name}!")\n\n\nif __name__ == "__main__":\n    main()\n',
            "README.md": "# {name}\n\nRun with `python3 main.py`.\n",
            ".gitignore": ".venv/\n__pycache__/\n",
        },
        "main.py",
    ),
    Template(
        "node",
        "Node.js",
        {
            "index.js": 'console.log("Hello from {name}!");\n',
            "package.json": '{{\n  "name": "{slug}",\n  "version": "0.1.0",\n  "main": "index.js",\n  "scripts": {{ "start": "node index.js" }}\n}}\n',
            ".gitignore": "node_modules/\n",
        },
        "index.js",
    ),
    Template(
        "web",
        "Web (HTML/CSS/JS)",
        {
            "index.html": '<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <title>{name}</title>\n  <link rel="stylesheet" href="style.css">\n</head>\n<body>\n  <h1>{name}</h1>\n  <script src="app.js"></script>\n</body>\n</html>\n',
            "style.css": "body {{ font-family: system-ui, sans-serif; margin: 2rem; }}\n",
            "app.js": 'console.log("{name} is ready");\n',
        },
        "index.html",
    ),
    Template(
        "csharp",
        "C# (.NET console)",
        {
            "Program.cs": 'Console.WriteLine("Hello from {name}!");\n',
            "{slug}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <OutputType>Exe</OutputType>\n    <TargetFramework>net10.0</TargetFramework>\n    <ImplicitUsings>enable</ImplicitUsings>\n    <Nullable>enable</Nullable>\n  </PropertyGroup>\n</Project>\n',
            ".gitignore": "bin/\nobj/\n",
        },
        "Program.cs",
    ),
]

TEMPLATES_BY_ID = {template.id: template for template in TEMPLATES}

VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]*$")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def create_project(parent: Path, name: str, template_id: str, git_init: bool = True) -> Path:
    """Create the project folder from a template and return its path."""
    name = name.strip()
    if not VALID_NAME.match(name):
        raise ValueError("Use letters, numbers, spaces, dots, dashes or underscores.")
    template = TEMPLATES_BY_ID[template_id]
    folder = Path(parent).expanduser() / name
    if folder.exists():
        raise FileExistsError(f"{folder} already exists.")

    values = {"name": name, "slug": slugify(name)}
    folder.mkdir(parents=True)
    for relative, content in template.files.items():
        target = folder / relative.format(**values)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.format(**values), encoding="utf-8")

    if git_init and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=folder, check=False)
    return folder
