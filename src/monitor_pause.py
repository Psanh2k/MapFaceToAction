"""監視の一時停止（ファイルフラグ）。"""

from __future__ import annotations

from pathlib import Path

from src.config import Config


def pause_file_path(config: Config) -> Path:
    """一時停止フラグのパス。"""
    return config.monitor_pause_absolute_path


def is_monitor_paused(config: Config) -> bool:
    """監視が一時停止中か。"""
    return pause_file_path(config).exists()


def pause_monitor(config: Config) -> Path:
    """監視を一時停止する。"""
    path = pause_file_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def resume_monitor(config: Config) -> bool:
    """監視を再開する。停止中だったら True。"""
    path = pause_file_path(config)
    if not path.exists():
        return False
    path.unlink()
    return True
