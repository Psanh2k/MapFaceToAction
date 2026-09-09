#!/usr/bin/env bash
# 監視 pause/resume を切り替え（ホットキー用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAUSE_FILE="$SCRIPT_DIR/data/.monitor_paused"

notify() {
    if command -v notify-send &>/dev/null; then
        notify-send "Face Chrome Killer" "$1"
    fi
}

if [ -f "$PAUSE_FILE" ]; then
    "$SCRIPT_DIR/scripts/resume-monitor.sh"
    notify "Monitor resumed"
else
    "$SCRIPT_DIR/scripts/pause-monitor.sh"
    notify "Monitor paused"
fi
