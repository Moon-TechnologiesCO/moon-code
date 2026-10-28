#!/usr/bin/env bash
# Construye moon-code_<version>_amd64.deb con todas sus dependencias Python incluidas.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml")"
PKG="moon-code_${VERSION}_amd64"
STAGE="$ROOT/build/$PKG"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/moon-code" \
         "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/doc/moon-code"

# Código y dependencias en /usr/lib/moon-code (sin depender de pip en el equipo del usuario).
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
"$PYTHON" -m pip install --quiet --upgrade --target "$STAGE/usr/lib/moon-code" "$ROOT"

cat > "$STAGE/usr/bin/moon" <<'WRAP'
#!/bin/sh
PYTHONPATH=/usr/lib/moon-code exec python3 -m moon "$@"
WRAP
chmod 755 "$STAGE/usr/bin/moon"

# Quitar artefactos de build que no sirven en el paquete.
find "$STAGE/usr/lib/moon-code" -name "__pycache__" -prune -exec rm -rf {} +
rm -rf "$STAGE/usr/lib/moon-code/bin"

install -m 644 "$ROOT/packaging/debian/moon-code.desktop" "$STAGE/usr/share/applications/moon-code.desktop"
install -m 644 "$ROOT/packaging/icons/moon-code.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/moon-code.svg"
install -m 644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/moon-code/copyright"

cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: moon-code
Version: $VERSION
Section: devel
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.11)
Maintainer: Moon Technologies <https://github.com/Moon-TechnologiesCO/moon-code>
Homepage: https://github.com/Moon-TechnologiesCO/moon-code
Description: Moon Code, editor de código para la terminal
 Explorador de archivos, pestañas con resaltado de sintaxis, temas Moon
 y chat de IA local con Ollama. Se abre desde el menú de aplicaciones
 dentro de una terminal.
CONTROL

mkdir -p "$ROOT/dist"
dpkg-deb --root-owner-group --build "$STAGE" "$ROOT/dist/$PKG.deb"
echo "Creado: $ROOT/dist/$PKG.deb"
