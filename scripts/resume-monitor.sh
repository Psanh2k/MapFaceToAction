#!/usr/bin/env bash
# 監視を再開
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAUSE_FILE="$SCRIPT_DIR/data/.monitor_paused"

if [ -f "$PAUSE_FILE" ]; then
    rm -f "$PAUSE_FILE"
    echo "Monitor resumed."
else
    echo "Monitor was not paused."
fi
