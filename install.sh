#!/usr/bin/env bash
# Per-user installation; never requires root.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/focusfield/app"
mkdir -p "$TARGET/assets" "${XDG_DATA_HOME:-$HOME/.local/share}/applications" "$HOME/.local/bin"
cp "$HERE/app.py" "$HERE/core.py" "$HERE/run.sh" "$TARGET/"
cp "$HERE/assets/focusfield.png" "$TARGET/assets/"
chmod +x "$TARGET/run.sh"
cat > "$HOME/.local/bin/focusfield" <<EOF
#!/usr/bin/env bash
exec "$TARGET/run.sh" "\$@"
EOF
chmod +x "$HOME/.local/bin/focusfield"
cat > "${XDG_DATA_HOME:-$HOME/.local/share}/applications/focusfield.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Focusfield
GenericName=Pomodoro Focus Timer
Comment=Find your flow, one session at a time
Exec="$TARGET/run.sh"
Icon="$TARGET/assets/focusfield.png"
Terminal=false
Categories=Utility;Office;
StartupNotify=true
EOF
if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" >/dev/null 2>&1 || true
fi
printf '\nInstalled Focusfield!\nOpen “Focusfield” from your applications menu, or run:\n  %s\n\n' "$HOME/.local/bin/focusfield"
