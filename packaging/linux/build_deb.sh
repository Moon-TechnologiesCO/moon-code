#!/usr/bin/env bash
# Build dist/moon-code_<version>_amd64.deb with every Python dependency bundled.
#   PYTHON=python3.12 packaging/linux/build_deb.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml")"
PKG="moon-code_${VERSION}_amd64"
STAGE="$ROOT/build/$PKG"
LIB="$STAGE/usr/lib/moon-code"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$LIB" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" "$STAGE/usr/share/doc/moon-code"

# 1. Moon Code and its dependencies, so users don't need pip.
"$PYTHON" -m pip install --quiet --upgrade --target "$LIB" "$ROOT"
rm -rf "$LIB/bin"
find "$LIB" -name "__pycache__" -prune -exec rm -rf {} +

# 2. tree-sitter's core is compiled per Python version. Add the binary for every CPython that
#    Ubuntu/Debian ship (3.10 – 3.14); Python loads the one whose ABI tag matches.
TS_VERSION="$("$PYTHON" -c 'import importlib.metadata as m; print(m.version("tree-sitter"))')"
WHEELS="$(mktemp -d)"
for py in 3.10 3.11 3.12 3.13 3.14; do
  "$PYTHON" -m pip download --quiet --no-deps --only-binary=:all: --dest "$WHEELS" \
    --python-version "$py" --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
    "tree-sitter==$TS_VERSION" || echo "warning: no tree-sitter wheel for Python $py"
done
for wheel in "$WHEELS"/*.whl; do
  "$PYTHON" - "$wheel" "$LIB" <<'PY'
import sys, zipfile
wheel, target = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(wheel) as archive:
    for name in archive.namelist():
        if name.startswith("tree_sitter/") and name.endswith(".so"):
            archive.extract(name, target)
PY
done
rm -rf "$WHEELS"

# 3. Launcher, menu entry and icons.
cat > "$STAGE/usr/bin/moon" <<'WRAP'
#!/bin/sh
PYTHONPATH=/usr/lib/moon-code exec python3 -m moon "$@"
WRAP
chmod 755 "$STAGE/usr/bin/moon"

install -m 644 "$ROOT/packaging/linux/moon-code.desktop" "$STAGE/usr/share/applications/moon-code.desktop"
install -m 644 "$ROOT/packaging/icons/moon-code.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/moon-code.svg"
for size in 16 32 48 64 128 256 512; do
  dir="$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$dir"
  install -m 644 "$ROOT/packaging/icons/png/$size.png" "$dir/moon-code.png"
done
install -m 644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/moon-code/copyright"

# 4. Package metadata.
SIZE_KB="$(du -sk "$STAGE/usr" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: moon-code
Version: $VERSION
Section: devel
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.10)
Recommends: git, ripgrep
Suggests: ollama
Installed-Size: $SIZE_KB
Maintainer: Moon Technologies <https://github.com/Moon-TechnologiesCO/moon-code>
Homepage: https://moon-technologiesco.github.io/moon-code/
Description: Moon Code, the code editor that lives in your terminal
 A VS Code style editor for the terminal: file explorer, tabs, syntax
 highlighting, autocomplete, find and replace, an integrated terminal,
 one-key run for dozens of languages, extensions and a local AI chat
 powered by Ollama.
CONTROL

mkdir -p "$ROOT/dist"
dpkg-deb --root-owner-group --build "$STAGE" "$ROOT/dist/$PKG.deb" >/dev/null
echo "Built $ROOT/dist/$PKG.deb"
