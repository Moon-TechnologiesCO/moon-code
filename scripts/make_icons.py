"""Render the app icon (packaging/icons/moon-code.svg) to PNG sizes and a macOS .icns. Developer tool.

    python scripts/make_icons.py      # needs cairosvg and Pillow
"""

from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "packaging" / "icons"
SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]


def main() -> None:
    svg = ICONS / "moon-code.svg"
    png_dir = ICONS / "png"
    png_dir.mkdir(exist_ok=True)
    for size in SIZES:
        cairosvg.svg2png(url=str(svg), write_to=str(png_dir / f"{size}.png"), output_width=size, output_height=size)
    Image.open(png_dir / "1024.png").save(ICONS / "moon-code.icns", sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512, 1024)])
    print(f"Icons written to {ICONS}")


if __name__ == "__main__":
    main()
