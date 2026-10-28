"""Save a Textual screenshot as SVG that renders Moon Code's icons correctly. Developer tool.

Textual's SVG uses the Fira Code web font, which has no Nerd Font icons, and browsers don't fall
back to installed symbol fonts inside SVG. This embeds Symbols Nerd Font and drops the duplicate
traffic lights of the screenshot frame (the app draws its own).
"""

import re
from pathlib import Path

FONT = Path(__file__).resolve().parents[1] / "packaging" / "fonts" / "SymbolsNerdFontMono-Regular.ttf"
FRAME_DOTS = re.compile(r'<g transform="translate\(26,22\)">.*?</g>', re.S)
FONT_FACE = "@font-face {{ font-family: 'Moon Symbols'; src: url('{uri}') format('truetype'); }}\n"


def save(app, path: Path) -> Path:
    path = Path(path)
    app.save_screenshot(str(path))
    svg = FRAME_DOTS.sub("", path.read_text(), count=1)
    svg = svg.replace("font-family: Fira Code, monospace;", "font-family: Fira Code, 'Moon Symbols', monospace;")
    svg = svg.replace("<style>", "<style>\n" + FONT_FACE.format(uri=FONT.as_uri()), 1)
    path.write_text(svg)
    return path
