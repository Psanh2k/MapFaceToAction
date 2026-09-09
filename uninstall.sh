#!/usr/bin/env bash
# Face Chrome Killer アンインストールスクリプト
set -euo pipefail

echo "=== Face Chrome Killer - Uninstallation ==="

SERVICE_NAME="face-chrome-killer.service"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"

# サービス停止・無効化
if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
    echo "Stopping service..."
    systemctl --user stop "$SERVICE_NAME"
fi

if systemctl --user is-enabled "$SERVICE_NAME" &>/dev/null; then
    echo "Disabling service..."
    systemctl --user disable "$SERVICE_NAME"
fi

# サービスファイル削除
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    echo "Removed $SERVICE_FILE"
fi

systemctl --user daemon-reload 2>/dev/null || true

echo ""
echo "Service removed."
echo "Face data (data/face_encoding.pkl) was NOT deleted."
echo "To remove face data manually: rm data/face_encoding.pkl"
echo ""
