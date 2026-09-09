"""SkipPresenceTracker のテスト。"""

import numpy as np
from unittest.mock import patch

from src.config import Config
from src.face_recognition_service import FaceRecognitionService
from src.skip_presence_tracker import SkipPresenceTracker


def test_stranger_recently_present_within_grace():
    """猶予期間内は他人ありと判定。"""
    tracker = SkipPresenceTracker(grace_seconds=3.0)
    tracker._last_stranger_time = 100.0
    assert tracker.stranger_recently_present(101.5) is True
    assert tracker.stranger_recently_present(104.0) is False


def test_update_marks_multiple_faces(tmp_path):
    """複数顔検出時に他人フラグを立てる。"""
    config = Config()
    config.faces_skip_data_dir = tmp_path / "skip"
    config.faces_kill_data_dir = tmp_path / "kill"
    service = FaceRecognitionService(config, flow="skip")
    service.register_user("sanhdp", np.random.rand(128), source="webcam")

    tracker = SkipPresenceTracker(grace_seconds=3.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch.object(service, "count_skip_presence", return_value=(2, 1, 0)):
        tracker.update(service, frame, now=10.0)

    assert tracker.stranger_recently_present(11.0) is True
