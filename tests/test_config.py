"""設定モジュールのテスト。"""

import os
from unittest.mock import patch

from src.config import Config, get_config


def test_default_config_values():
    """デフォルト設定値が正しいこと（.env 未読込）。"""
    env_patch = {
        "CAMERA_INDEX": None,
        "CAMERA_WIDTH": None,
        "DRY_RUN": None,
    }
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
        assert config.camera_index == 0
        assert config.camera_width == 640
        assert config.camera_height == 480
        assert config.face_match_threshold == 0.50
        assert config.required_match_seconds == 2.0
        assert config.require_single_face is True
        assert config.dry_run is False
        assert config.motion_skip_registered_face is True
        assert config.chrome_kill_on_face_match is True
        assert "google-chrome" in config.chrome_process_names


def test_get_config_returns_instance():
    """get_config が Config インスタンスを返すこと。"""
    config = get_config()
    assert isinstance(config, Config)


def test_recognition_interval_seconds():
    """認識間隔の秒換算が正しいこと。"""
    config = Config()
    assert config.recognition_interval_seconds == config.recognition_interval_ms / 1000.0
