"""motion_skip のテスト。"""

import numpy as np

from src.face_recognition_service import FaceRecognitionService
from src.motion_detector import MotionEvent
from src.motion_skip import motion_near_skip_face, should_skip_motion_minimize


def test_motion_far_from_skip_face(tmp_path):
    """skip 顔から離れた動体は minimize 対象。"""
    from unittest.mock import patch
    from src.config import Config

    config = Config()
    config.faces_skip_data_dir = tmp_path / "skip"
    config.faces_kill_data_dir = tmp_path / "kill"
    service = FaceRecognitionService(config, flow="skip")
    service.register_user("sanhdp", np.random.rand(128), source="webcam")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    face_bbox = (200, 100, 400, 300)
    motion = MotionEvent(detected=True, bbox=(0, 0, 60, 60), area=3600)

    assert motion_near_skip_face(motion, face_bbox, margin_ratio=0.5, overlap_ratio=0.25) is False
    with patch.object(service, "get_primary_skip_face_bbox", return_value=face_bbox):
        assert should_skip_motion_minimize(
            service,
            frame,
            motion,
            face_margin_ratio=0.5,
            motion_overlap_ratio=0.25,
        ) is False


def test_motion_near_skip_face(tmp_path):
    """skip 顔付近の動体は minimize しない。"""
    from src.config import Config

    config = Config()
    config.faces_skip_data_dir = tmp_path / "skip"
    config.faces_kill_data_dir = tmp_path / "kill"
    service = FaceRecognitionService(config, flow="skip")
    service.register_user("sanhdp", np.random.rand(128), source="webcam")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    face_bbox = (200, 100, 400, 300)
    motion = MotionEvent(detected=True, bbox=(250, 150, 80, 80), area=6400)

    assert motion_near_skip_face(motion, face_bbox, margin_ratio=0.8, overlap_ratio=0.25) is True
