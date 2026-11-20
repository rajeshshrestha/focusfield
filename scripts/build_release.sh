#!/usr/bin/env bash
# Build Linux distribution archives from the checked-out source tree.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid VERSION: $VERSION" >&2; exit 1; }
OUT="${1:-$ROOT/dist}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

for file in app.py core.py README.md CHANGELOG.md run.sh install.sh uninstall.sh assets/focusfield.png; do
  test -f "$ROOT/$file" || { echo "Missing: $file" >&2; exit 1; }
done

# Create a portable archive that preserves executable bits on shell scripts.
ROOT="$ROOT" OUT="$OUT" python3 - <<'PY'
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(os.environ["ROOT"])
out = Path(os.environ["OUT"]) / "Focusfield_Linux_Portable.zip"
files = [
    "app.py", "core.py", "README.md", "CHANGELOG.md",
    "run.sh", "install.sh", "uninstall.sh", "VERSION", "tests/test_core.py",
]
files += [str(p.relative_to(root)) for p in sorted((root / "assets").glob("*.png"))]
with ZipFile(out, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
    for name in files:
        archive.write(root / name, arcname="Focusfield/" + name)
print(f"Built {out}")
PY

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Note: dpkg-deb is unavailable. Portable ZIP generated; skipping .deb." >&2
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/DEBIAN" "$TMP/usr/bin" "$TMP/usr/share/focusfield/assets" \
         "$TMP/usr/share/applications" "$TMP/usr/share/doc/focusfield" \
         "$TMP/usr/share/icons/hicolor/256x256/apps"
install -m 644 "$ROOT/app.py" "$ROOT/core.py" "$TMP/usr/share/focusfield/"
install -m 644 "$ROOT/assets/focusfield.png" "$TMP/usr/share/focusfield/assets/"
install -m 644 "$ROOT/assets/focusfield.png" "$TMP/usr/share/icons/hicolor/256x256/apps/"
install -m 644 "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$TMP/usr/share/doc/focusfield/"
cat > "$TMP/usr/bin/focusfield" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 /usr/share/focusfield/app.py "$@"
LAUNCHER
chmod 755 "$TMP/usr/bin/focusfield"
cat > "$TMP/usr/share/applications/focusfield.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Version=1.0
Name=Focusfield
GenericName=Pomodoro Focus Timer
Comment=Find your flow, one session at a time
Exec=focusfield
Icon=focusfield
Terminal=false
Categories=Utility;Office;
StartupNotify=true
DESKTOP
cat > "$TMP/DEBIAN/control" <<CONTROL
Package: focusfield
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-tk
Maintainer: Rajesh Shrestha <rajesh.45npt@gmail.com>
Description: Calm and private Pomodoro focus timer for Linux
 Focusfield is an offline desktop timer with customizable breaks,
 task tracking, daily goals, progress charts, and notifications.
CONTROL
chmod 644 "$TMP/DEBIAN/control"
dpkg-deb --build --root-owner-group "$TMP" "$OUT/focusfield_${VERSION}_all.deb" >/dev/null
printf 'Built %s\n' "$OUT/focusfield_${VERSION}_all.deb"

(cd "$OUT" && sha256sum "focusfield_${VERSION}_all.deb" Focusfield_Linux_Portable.zip > SHA256SUMS)
printf 'Built %s\n' "$OUT/SHA256SUMS"
