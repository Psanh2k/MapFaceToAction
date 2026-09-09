"""顔認識サービスのテスト。"""

import os
import pickle
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.config import Config
from src.face_recognition_service import FaceRecognitionService


def _make_config(tmp_path: Path) -> Config:
    """テスト用 Config。"""
    config = Config()
    config.face_encoding_path = tmp_path / "face_encoding.pkl"
    return config


def test_save_and_load_encoding(tmp_path):
    """顔エンコーディングの保存と読み込み。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)

    encoding = np.random.rand(128)
    save_path = service.save_encoding(encoding)
    assert save_path.exists()

    service2 = FaceRecognitionService(config)
    service2.load_registered_face()
    assert service2.is_loaded
    np.testing.assert_array_almost_equal(
        service2._registered_encoding, encoding
    )


def test_is_match_with_same_encoding(tmp_path):
    """同一エンコーディング → MATCH。"""
    config = _make_config(tmp_path)
    config.face_match_threshold = 0.50
    service = FaceRecognitionService(config)

    encoding = np.random.rand(128)
    service.save_encoding(encoding)
    service.load_registered_face()

    assert service.is_match(encoding) is True


def test_is_match_with_different_encoding(tmp_path):
    """異なるエンコーディング → NO MATCH。"""
    config = _make_config(tmp_path)
    config.face_match_threshold = 0.50
    service = FaceRecognitionService(config)

    encoding = np.random.rand(128)
    service.save_encoding(encoding)
    service.load_registered_face()

    different = np.random.rand(128)
    assert service.is_match(different) is False


def test_validate_sample_consistency():
    """サンプル一貫性検証。"""
    config = Config()
    config.face_match_threshold = 0.50
    service = FaceRecognitionService(config)

    base = np.random.rand(128)
    similar = base + np.random.rand(128) * 0.01
    encodings = [base, similar, base + np.random.rand(128) * 0.005]
    assert service.validate_sample_consistency(encodings) is True


def test_validate_inconsistent_samples():
    """不一致サンプル → 検証失敗。"""
    config = Config()
    config.face_match_threshold = 0.10
    service = FaceRecognitionService(config)

    encodings = [np.random.rand(128), np.random.rand(128)]
    assert service.validate_sample_consistency(encodings) is False


def test_analyze_frame_no_face():
    """Test 1: 顔なし。"""
    config = Config()
    service = FaceRecognitionService(config)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("src.face_recognition_service.face_recognition.face_locations", return_value=[]):
        count, matched, _ = service.analyze_frame(frame)
        assert count == 0
        assert matched is False


def test_analyze_frame_multiple_faces(tmp_path):
    """Test 5: 複数顔 → トリガー条件不成立。"""
    config = _make_config(tmp_path)
    config.require_single_face = True
    service = FaceRecognitionService(config)
    service.save_encoding(np.random.rand(128))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    locations = [(10, 100, 100, 10), (10, 200, 100, 110)]
    with patch(
        "src.face_recognition_service.face_recognition.face_locations",
        return_value=locations,
    ):
        count, matched, _ = service.analyze_frame(frame)
        assert count == 2
        assert matched is False


def test_register_from_image_file(tmp_path):
    """画像ファイルからの登録。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    encoding = np.random.rand(128)
    locations = [(10, 100, 100, 10)]

    with patch(
        "src.face_recognition_service.face_recognition.load_image_file",
        return_value=np.zeros((480, 640, 3), dtype=np.uint8),
    ), patch(
        "src.face_recognition_service.face_recognition.face_locations",
        return_value=locations,
    ), patch(
        "src.face_recognition_service.face_recognition.face_encodings",
        return_value=[encoding],
    ):
        image_file = tmp_path / "person.jpg"
        image_file.write_bytes(b"fake")
        save_path = service.register_from_image_file(image_file)

    assert save_path.exists()
    service.load_registered_face()
    assert service.is_match(encoding)


def test_register_from_image_multiple_faces(tmp_path):
    """複数顔の画像は拒否。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)

    with patch(
        "src.face_recognition_service.face_recognition.load_image_file",
        return_value=np.zeros((480, 640, 3), dtype=np.uint8),
    ), patch(
        "src.face_recognition_service.face_recognition.face_locations",
        return_value=[(10, 100, 100, 10), (10, 200, 100, 110)],
    ), pytest.raises(ValueError, match="Multiple faces"):
        group_file = tmp_path / "group.jpg"
        group_file.write_bytes(b"fake")
        service.register_from_image_file(group_file)


def test_encoding_file_permissions(tmp_path):
    """保存ファイルの権限が 600 であること。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    save_path = service.save_encoding(np.random.rand(128))

    if os.name != "nt":
        mode = save_path.stat().st_mode & 0o777
        assert mode == 0o600
