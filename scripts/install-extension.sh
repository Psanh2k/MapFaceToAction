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

# 次回ログイン時に自動有効化（gsettings）
if command -v gsettings &>/dev/null; then
    python3 - <<PY
import ast
import subprocess

uuid = "$EXT_UUID"
result = subprocess.run(
    ["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
    capture_output=True,
    text=True,
    check=True,
)
exts = ast.literal_eval(result.stdout.strip())
if uuid not in exts:
    exts.append(uuid)
    formatted = "[" + ", ".join(f"'{e}'" for e in exts) + "]"
    subprocess.run(
        ["gsettings", "set", "org.gnome.shell", "enabled-extensions", formatted],
        check=True,
    )
    print(f"Pre-enabled for next login: {uuid}")
else:
    print(f"Already in enabled-extensions: {uuid}")
PY
fi

if command -v gnome-extensions &>/dev/null; then
    gnome-extensions enable "$EXT_UUID" 2>/dev/null || true
fi

echo "Extension installed: $EXT_UUID"
echo ""

SHELL_PID="$(pgrep -u "$(id -u)" -x gnome-shell 2>/dev/null | head -1 || true)"
if [ -n "$SHELL_PID" ]; then
    SHELL_START="$(ps -o lstart= -p "$SHELL_PID" 2>/dev/null | xargs || true)"
    echo "GNOME Shell session started: ${SHELL_START:-unknown}"
    echo "Extension was just copied to disk — Shell will NOT see it until you log out/in."
fi

if command -v gnome-extensions &>/dev/null; then
    if gnome-extensions list 2>/dev/null | grep -qx "$EXT_UUID"; then
        echo "Extension is registered with GNOME Shell."
    else
        echo "Extension is on disk but NOT registered yet (expected before re-login)."
    fi
fi

echo ""
echo "IMPORTANT: Log out and log back in (or reboot) to load the extension."
echo "Closing the terminal is NOT enough — you must end the GNOME session."
echo ""
echo "After re-login, verify:"
echo "  gnome-extensions list --enabled | grep $EXT_UUID"
echo "  gdbus call --session --dest org.gnome.Shell --object-path /org/mapface/ChromeMinimize --method org.mapface.ChromeMinimize.MinimizeChrome"
echo ""
echo "Then test:"
echo "  cd $SCRIPT_DIR"
echo "  .venv/bin/python main.py --test-chrome-minimize"
