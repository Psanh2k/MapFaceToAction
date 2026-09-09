"""顔認識サービスのテスト。"""

import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.config import Config
from src.face_recognition_service import FaceRecognitionService


def _make_config(tmp_path: Path) -> Config:
    """テスト用 Config。"""
    config = Config()
    config.faces_kill_data_dir = tmp_path / "faces" / "kill"
    config.faces_skip_data_dir = tmp_path / "faces" / "skip"
    config.faces_data_dir = tmp_path / "faces" / "kill"
    config.face_encoding_path = tmp_path / "face_encoding.pkl"
    return config


def test_kill_and_skip_flows_are_separate(tmp_path):
    """kill / skip フローのユーザーは独立。"""
    config = _make_config(tmp_path)
    kill_service = FaceRecognitionService(config, flow="kill")
    skip_service = FaceRecognitionService(config, flow="skip")

    kill_service.register_user("alice", np.random.rand(128), source="webcam")
    skip_service.register_user("bob", np.random.rand(128), source="webcam")

    assert kill_service.list_users() == ["alice"]
    assert skip_service.list_users() == ["bob"]


def test_register_and_match_multiple_users(tmp_path):
    """複数ユーザー登録と照合。"""
    config = _make_config(tmp_path)
    config.face_match_threshold = 0.50
    service = FaceRecognitionService(config, flow="kill")

    enc_alice = np.random.rand(128)
    enc_bob = np.random.rand(128)
    service.register_user("alice", enc_alice, source="webcam")
    service.register_user("bob", enc_bob, source="image")
    service.load_registered_faces()

    assert service.is_match(enc_alice) is True
    assert service.last_matched_user == "alice"
    assert service.is_match(enc_bob) is True
    assert service.last_matched_user == "bob"
    assert service.is_match(np.random.rand(128)) is False


def test_delete_user(tmp_path):
    """ユーザー削除。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    enc = np.random.rand(128)
    service.register_user("alice", enc, source="webcam")
    assert service.delete_user("alice") is True
    assert service.list_users() == []


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
    with patch(
        "src.face_recognition_service.face_recognition.face_locations",
        return_value=[],
    ):
        count, matched, _, user = service.analyze_frame(frame)
        assert count == 0
        assert matched is False
        assert user is None


def test_analyze_frame_multiple_faces(tmp_path):
    """Test 5: 複数顔 → トリガー条件不成立。"""
    config = _make_config(tmp_path)
    config.require_single_face = True
    service = FaceRecognitionService(config)
    service.register_user("alice", np.random.rand(128), source="webcam")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    locations = [(10, 100, 100, 10), (10, 200, 100, 110)]
    with patch(
        "src.face_recognition_service.face_recognition.face_locations",
        return_value=locations,
    ):
        count, matched, _, user = service.analyze_frame(frame)
        assert count == 2
        assert matched is False
        assert user is None


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
        save_path = service.register_from_image_file(image_file, "alice")

    assert save_path.exists()
    service.load_registered_faces()
    assert service.is_match(encoding) is True
    assert service.last_matched_user == "alice"


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
        service.register_from_image_file(group_file, "alice")


def test_load_registered_faces_if_any_empty(tmp_path):
    """未登録時は False、例外なし。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)

    assert service.load_registered_faces_if_any() is False
    assert service.is_loaded is False


def test_has_registered_user_in_frame_without_loaded_users(tmp_path):
    """未登録時は has_registered_user_in_frame が False。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    assert service.has_registered_user_in_frame(frame) is False


def test_should_skip_motion_minimize_only_skip_user(tmp_path):
    """skip ユーザーのみなら minimize をスキップ。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config, flow="skip")
    skip_enc = np.random.rand(128)
    service.register_user("sanhdp", skip_enc, source="webcam")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch.object(
        service,
        "_encode_all_faces_in_frame",
        return_value=(1, [skip_enc]),
    ), patch.object(service, "find_matching_user", return_value="sanhdp"):
        assert service.should_skip_motion_minimize(frame) is True


def test_should_skip_motion_minimize_with_stranger(tmp_path):
    """skip ユーザー + 他人がいれば minimize する（skip しない）。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config, flow="skip")
    skip_enc = np.random.rand(128)
    stranger_enc = np.random.rand(128)
    service.register_user("sanhdp", skip_enc, source="webcam")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def match_side_effect(encoding):
        if np.array_equal(encoding, skip_enc):
            return "sanhdp"
        return None

    with patch.object(
        service,
        "_encode_all_faces_in_frame",
        return_value=(2, [skip_enc, stranger_enc]),
    ), patch.object(service, "find_matching_user", side_effect=match_side_effect):
        assert service.should_skip_motion_minimize(frame) is False


def test_has_registered_user_in_frame(tmp_path):
    """登録ユーザー検出時のみ True。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    service.register_user("alice", np.random.rand(128), source="webcam")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch.object(
        service,
        "analyze_frame",
        return_value=(1, True, np.random.rand(128), "alice"),
    ):
        assert service.has_registered_user_in_frame(frame) is True

    with patch.object(
        service,
        "analyze_frame",
        return_value=(1, False, None, None),
    ):
        assert service.has_registered_user_in_frame(frame) is False


def test_encoding_file_permissions(tmp_path):
    """保存ファイルの権限が 600 であること。"""
    config = _make_config(tmp_path)
    service = FaceRecognitionService(config)
    save_path = service.register_user("alice", np.random.rand(128), source="webcam")

    if os.name != "nt":
        mode = save_path.stat().st_mode & 0o777
        assert mode == 0o600
