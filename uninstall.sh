#!/usr/bin/env bash
set -euo pipefail
rm -rf -- "${XDG_DATA_HOME:-$HOME/.local/share}/focusfield/app"
rm -f -- "$HOME/.local/bin/focusfield"
rm -f -- "${XDG_DATA_HOME:-$HOME/.local/share}/applications/focusfield.desktop"
printf 'Focusfield application uninstalled. Your saved sessions remain at %s\n' "${XDG_DATA_HOME:-$HOME/.local/share}/focusfield/state.json"
