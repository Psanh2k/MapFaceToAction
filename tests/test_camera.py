"""カメラモジュールのテスト。"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.camera import Camera, CameraError
from src.config import Config


def test_camera_open_failure():
    """Test 8: カメラ不可 → CameraError。"""
    config = Config()
    camera = Camera(config)

    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = False

    with patch("src.camera.cv2.VideoCapture", return_value=mock_capture):
        with pytest.raises(CameraError):
            camera.open()


def test_camera_read_without_open():
    """未オープン状態での read は CameraError。"""
    config = Config()
    camera = Camera(config)

    with pytest.raises(CameraError):
        camera.read()


def test_camera_release_idempotent():
    """release は複数回呼んでも安全。"""
    config = Config()
    camera = Camera(config)
    camera.release()
    camera.release()


def test_camera_read_success():
    """正常フレーム読み取り。"""
    config = Config()
    camera = Camera(config)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, frame)

    with patch("src.camera.cv2.VideoCapture", return_value=mock_capture):
        camera.open()
        result = camera.read()
        assert result is not None
        assert result.shape == (480, 640, 3)
        camera.release()
