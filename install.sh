#!/usr/bin/env bash
# Face Chrome Killer インストールスクリプト
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Face Chrome Killer - Installation ==="

# OS チェック
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "OS: $PRETTY_NAME"
else
    echo "Warning: Cannot detect OS version"
fi

# Python チェック
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PYTHON_VERSION"

MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
    echo "Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi

# ネイティブビルド依存（dlib 用）
if ! dpkg -s cmake &>/dev/null 2>&1; then
    echo "Note: cmake not installed. You may need:"
    echo "  sudo apt install cmake build-essential libopenblas-dev"
fi

# 仮想環境
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# ディレクトリ作成
mkdir -p data logs

# .env コピー（既存は上書きしない）
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
else
    echo ".env already exists, not overwriting"
fi

# 権限設定
chmod 700 data 2>/dev/null || true
if [ -f "data/face_encoding.pkl" ]; then
    chmod 600 data/face_encoding.pkl
fi

# systemd ユーザーサービス
SERVICE_SRC="$SCRIPT_DIR/systemd/face-chrome-killer.service"
SERVICE_DST="$HOME/.config/systemd/user/face-chrome-killer.service"

# パスを実際のインストール先に置換
sed "s|%h/Workspace/Project/MapFaceToAction|$SCRIPT_DIR|g" "$SERVICE_SRC" > "$SERVICE_DST"

mkdir -p "$HOME/.config/systemd/user"
systemctl --user daemon-reload

# GNOME Shell 拡張（Wayland で Chrome minimize 用）
EXT_UUID="face-chrome-killer-minimize@mapface"
EXT_SRC="$SCRIPT_DIR/extension/$EXT_UUID"
EXT_DST="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

if [ -d "$EXT_SRC" ]; then
    mkdir -p "$HOME/.local/share/gnome-shell/extensions"
    rm -rf "$EXT_DST"
    cp -r "$EXT_SRC" "$EXT_DST"
    if command -v gnome-extensions &>/dev/null; then
        gnome-extensions enable "$EXT_UUID" 2>/dev/null || true
        echo "GNOME extension installed: $EXT_UUID"
        echo "  -> Log out and log back in (or restart GNOME Shell) to activate"
    else
        echo "Install gnome-extensions CLI: sudo apt install gnome-shell-extension-prefs"
    fi
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. source .venv/bin/activate"
echo "  2. python register.py          # Register your face"
echo "  3. DRY_RUN=true python main.py # Test without killing Chrome"
echo "  4. Edit .env: set DRY_RUN=false for production"
echo "  5. systemctl --user enable --now face-chrome-killer.service"
echo ""
