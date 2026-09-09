#!/usr/bin/env bash
# GNOME Shell 拡張インストール（Wayland で Chrome minimize 用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_UUID="face-chrome-killer-minimize@mapface"
EXT_SRC="$SCRIPT_DIR/extension/$EXT_UUID"
EXT_DST="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

if [ ! -d "$EXT_SRC" ]; then
    echo "Error: extension source not found at $EXT_SRC"
    exit 1
fi

mkdir -p "$HOME/.local/share/gnome-shell/extensions"
rm -rf "$EXT_DST"
cp -r "$EXT_SRC" "$EXT_DST"

if [ ! -f "$EXT_DST/extension.js" ] || [ ! -f "$EXT_DST/metadata.json" ]; then
    echo "Error: extension files missing at $EXT_DST"
    exit 1
fi

if command -v gnome-extensions &>/dev/null; then
    gnome-extensions enable "$EXT_UUID" 2>/dev/null || true
fi

echo "Extension installed: $EXT_UUID"
echo ""

if command -v gnome-extensions &>/dev/null; then
    if gnome-extensions list 2>/dev/null | grep -qx "$EXT_UUID"; then
        echo "Extension is registered with GNOME Shell."
    else
        echo "Extension is on disk but NOT loaded by GNOME Shell yet."
    fi
fi

echo ""
echo "IMPORTANT: Log out and log back in (or reboot) to load the extension."
echo "GNOME only discovers new extensions when the session starts."
echo ""
echo "After re-login, verify:"
echo "  gnome-extensions list --enabled | grep $EXT_UUID"
echo "  gdbus call --session --dest org.gnome.Shell --object-path /org/mapface/ChromeMinimize --method org.mapface.ChromeMinimize.MinimizeChrome"
echo ""
echo "Then test:"
echo "  cd $SCRIPT_DIR"
echo "  .venv/bin/python main.py --test-chrome-minimize"
