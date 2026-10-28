"""Record the website demo videos by driving the real app. Developer tool.

    python scripts/record_demo.py docs/media

Each scene is scripted with Textual's test pilot, captured as SVG frames, rendered to PNG with
headless Chrome and joined into an MP4 with ffmpeg. Needs google-chrome (or chromium) and ffmpeg.
Set MOON_DEMO_AI=0 to skip the scene that talks to a local Ollama model.
"""

import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SIZE = (132, 38)
# MOON_DEMO_ONLY=power-tools,moon-ai re-renders just those videos (earlier scenes still run for state).
ONLY = {name for name in os.environ.get("MOON_DEMO_ONLY", "").split(",") if name}
WINDOW = "1600,960"

WORK = Path(tempfile.mkdtemp(prefix="moon-demo-"))
CONFIG = WORK / "config"
PROJECTS = WORK / "Projects"
SHELL = WORK / "demo-shell.sh"

# Isolate the demo from the real user: own settings, own projects folder, clean prompt.
os.environ["MOON_CONFIG_DIR"] = str(CONFIG)
SHELL.write_text("#!/bin/sh\nexport PS1='\\[\\e[1;35m\\]❯\\[\\e[0m\\] \\[\\e[1;34m\\]\\W\\[\\e[0m\\] '\n"
                 "exec bash --norc --noprofile -i\n")
SHELL.chmod(0o755)
os.environ["SHELL"] = str(SHELL)

from moon.core.config import Settings  # noqa: E402  (after MOON_CONFIG_DIR is set)
from moon.ui.app import MoonCode  # noqa: E402

FRAME_DOTS = re.compile(r'<g transform="translate\(26,22\)">.*?</g>', re.S)


class Recorder:
    def __init__(self, app: MoonCode, frames: Path):
        self.app = app
        self.frames = frames
        self.shots: list[tuple[Path, float]] = []

    def shot(self, seconds: float = 1.2) -> None:
        path = self.frames / f"{len(self.shots):04d}.svg"
        self.app.save_screenshot(str(path))
        # The app draws its own macOS traffic lights; drop the duplicate ones from the SVG frame.
        path.write_text(FRAME_DOTS.sub("", path.read_text(), count=1))
        self.shots.append((path, seconds))


async def settle(pilot, seconds: float = 0.3) -> None:
    await pilot.pause()
    await asyncio.sleep(seconds)
    await pilot.pause()


async def type_text(pilot, rec: Recorder, text: str, every: int = 3, seconds: float = 0.12) -> None:
    for index, char in enumerate(text, start=1):
        await pilot.press(KEY_NAMES.get(char, char))
        if index % every == 0 or index == len(text):
            await pilot.pause()
            rec.shot(seconds)


KEY_NAMES = {" ": "space", "-": "minus", "(": "left_parenthesis", ")": "right_parenthesis",
             '"': "quotation_mark", ":": "colon", ".": "full_stop", ",": "comma", "_": "underscore",
             "\n": "enter", "=": "equals_sign", "{": "left_curly_bracket", "}": "right_curly_bracket",
             "/": "slash", "'": "apostrophe", "*": "asterisk", "+": "plus", "#": "number_sign",
             "[": "left_square_bracket", "]": "right_square_bracket", "<": "less_than_sign",
             ">": "greater_than_sign", "?": "question_mark", "!": "exclamation_mark"}


async def scene_getting_started(rec: Recorder, pilot) -> None:
    app = rec.app
    rec.shot(2.5)
    await pilot.press("p")
    await settle(pilot)
    rec.shot(1.0)
    await type_text(pilot, rec, "hello-moon", every=2)
    rec.shot(1.2)
    await pilot.press("enter")
    await settle(pilot, 1.0)
    rec.shot(1.0)
    workspace = app.screen
    await settle(pilot, 0.8)
    rec.shot(2.5)
    workspace.action_show_view("explorer")
    await settle(pilot)


async def scene_code_and_run(rec: Recorder, pilot) -> None:
    workspace = rec.app.screen
    editor = workspace.active_editor
    editor.focus()
    editor.move_cursor(editor.document.end)
    await settle(pilot)
    rec.shot(1.2)
    # Auto-indent after ":" and indent-aware backspace do the indentation, like in VS Code.
    await type_text(pilot, rec, "\n\ndef fibonacci(count):\n", every=4)
    await type_text(pilot, rec, "numbers = [0, 1]\n", every=4)
    await type_text(pilot, rec, "while len(numbers) < count:\n", every=4)
    await type_text(pilot, rec, "numbers.append(numbers[-1] + numbers[-2])\n", every=6)
    await pilot.press("backspace")
    await type_text(pilot, rec, "return numbers\n", every=4)
    await pilot.press("backspace")
    # Autocomplete: type "fib", the suggestion appears, Tab accepts it.
    await type_text(pilot, rec, "\nprint(fib", every=3)
    await settle(pilot, 0.2)
    rec.shot(2.0)
    await pilot.press("tab")
    await type_text(pilot, rec, "(10))", every=5)
    await settle(pilot)
    rec.shot(1.5)
    await pilot.press("ctrl+s")
    await settle(pilot)
    await pilot.press("f5")
    await settle(pilot, 1.5)
    rec.shot(1.0)
    await settle(pilot, 1.0)
    rec.shot(3.0)


async def scene_power_tools(rec: Recorder, pilot) -> None:
    workspace = rec.app.screen
    project = workspace.root
    (project / "utils.py").write_text('def slugify(text):\n    """TODO: handle accents"""\n    return text.lower().replace(" ", "-")\n')
    (project / "notes.md").write_text("# Notes\n\nTODO: write the README.\n")
    workspace.action_refresh_explorer()
    await settle(pilot)
    workspace.active_editor.focus()
    await pilot.press("ctrl+p")
    await settle(pilot)
    rec.shot(1.0)
    await type_text(pilot, rec, "uti", every=1, seconds=0.4)
    rec.shot(1.2)
    await pilot.press("enter")
    await settle(pilot)
    rec.shot(1.5)
    await pilot.press("f1")
    await settle(pilot)
    rec.shot(1.2)
    await type_text(pilot, rec, "color theme", every=2, seconds=0.3)
    await settle(pilot, 0.5)
    rec.shot(1.5)
    await pilot.press("enter")
    await settle(pilot)
    rec.shot(1.2)
    await type_text(pilot, rec, "light", every=2, seconds=0.3)
    await pilot.press("enter")
    await settle(pilot, 0.5)
    rec.shot(2.5)
    rec.app.set_moon_theme("moon-night")
    await settle(pilot)
    workspace.action_show_view("search")
    await settle(pilot)
    await type_text(pilot, rec, "todo", every=1, seconds=0.3)
    await pilot.press("enter")
    await settle(pilot, 0.8)
    rec.shot(2.5)
    workspace.action_show_view("extensions")
    await settle(pilot)
    rec.shot(3.0)
    workspace.action_show_view("explorer")
    rec.app.set_moon_theme("moon-midnight")
    await settle(pilot, 0.5)
    rec.shot(2.0)
    rec.app.set_moon_theme("moon-night")
    await settle(pilot)


async def scene_ai(rec: Recorder, pilot) -> None:
    workspace = rec.app.screen
    workspace.open_file(workspace.root / "main.py")
    await settle(pilot)
    workspace.action_toggle_ai(force=True)
    await settle(pilot, 0.5)
    rec.shot(1.5)
    await type_text(pilot, rec, "What does fibonacci do? One sentence.", every=5)
    await pilot.press("enter")
    for _ in range(120):  # The answer streams in from the local model.
        await settle(pilot, 0.6)
        rec.shot(0.25)
        if not any(worker.is_running for worker in rec.app.workers):
            break
    rec.shot(4.0)


SCENES = [
    ("getting-started", scene_getting_started),
    ("code-and-run", scene_code_and_run),
    ("power-tools", scene_power_tools),
    ("moon-ai", scene_ai),
]


def chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(name):
            return name
    sys.exit("record_demo: needs google-chrome or chromium")


def render(shots: list[tuple[Path, float]], video: Path, poster: Path) -> None:
    browser = chrome()
    pngs = []
    for svg, seconds in shots:
        png = svg.with_suffix(".png")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={WINDOW}", f"--screenshot={png}", svg.as_uri()],
                       check=True, capture_output=True, timeout=60)
        pngs.append((png, seconds))
    concat = video.with_suffix(".txt")
    lines = [f"file '{png}'\nduration {seconds}" for png, seconds in pngs]
    concat.write_text("\n".join(lines) + f"\nfile '{pngs[-1][0]}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-vf", "scale=1600:-2,format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "26", "-movflags", "+faststart", str(video)], check=True)
    concat.unlink()
    shutil.copy(pngs[-1][0], poster)


async def record(out: Path) -> None:
    PROJECTS.mkdir(parents=True)
    Settings(projects_dir=str(PROJECTS), check_updates=False).save()
    app = MoonCode(None)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot, 0.5)
        for name, scene in SCENES:
            if name == "moon-ai" and os.environ.get("MOON_DEMO_AI") == "0":
                continue
            frames = WORK / name
            frames.mkdir()
            rec = Recorder(app, frames)
            print(f"Recording {name}…")
            await scene(rec, pilot)
            if name in ONLY or not ONLY:
                render(rec.shots, out / f"{name}.mp4", out / f"{name}.png")
            print(f"  {len(rec.shots)} frames → {out / (name + '.mp4')}")


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/media").resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(record(out))
    finally:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
