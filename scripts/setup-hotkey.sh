#!/usr/bin/env bash
# GNOME カスタムショートカットで pause/resume を登録（Wayland 対応）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINDING="${1:-<Super><Shift>p}"
KEY_ID="face-chrome-killer-pause"
TOGGLE_CMD="$SCRIPT_DIR/scripts/toggle-monitor.sh"

if [ ! -x "$TOGGLE_CMD" ]; then
    chmod +x "$TOGGLE_CMD"
fi

python3 - <<PY
import ast
import subprocess
import sys

binding = "$BINDING"
toggle_cmd = "$TOGGLE_CMD"
key_id = "$KEY_ID"
custom_base = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/{key_id}/"
schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{custom_base}"


def gget(*args: str) -> str:
    return subprocess.check_output(["gsettings", "get", *args], text=True).strip()


def gset(*args: str) -> None:
    subprocess.check_call(["gsettings", "set", *args])


raw = gget("org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings")
if raw.startswith("@as "):
    raw = raw[4:]
existing = ast.literal_eval(raw)
if custom_base not in existing:
    existing.append(custom_base)
    formatted = "[" + ", ".join(f"'{path}'" for path in existing) + "]"
    gset(
        "org.gnome.settings-daemon.plugins.media-keys",
        "custom-keybindings",
        formatted,
    )

gset(schema, "name", "Face Chrome Killer: Toggle Pause")
gset(schema, "command", toggle_cmd)
gset(schema, "binding", binding)
PY

echo "Hotkey registered: $BINDING"
echo "  Action: toggle pause/resume monitor"
echo "  Command: $TOGGLE_CMD"
echo ""
echo "Try pressing the shortcut, or run:"
echo "  $TOGGLE_CMD"
echo ""
echo "Change hotkey:"
echo "  $0 '<Control><Shift>p'"
