#!/usr/bin/env bash
# 監視を一時停止（minimize / kill しない）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAUSE_FILE="$SCRIPT_DIR/data/.monitor_paused"

mkdir -p "$SCRIPT_DIR/data"
touch "$PAUSE_FILE"

echo "Monitor paused."
echo "  Chrome will NOT be minimized while paused."
echo "  Resume: $SCRIPT_DIR/scripts/resume-monitor.sh"
