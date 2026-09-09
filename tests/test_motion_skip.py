"""motion_skip のテスト。"""

import numpy as np

from src.config import Config
from src.face_recognition_service import FaceRecognitionService
from src.motion_detector import MotionEvent
from src.motion_skip import has_second_person_motion, should_skip_motion_minimize
from src.skip_face_tracker import SkipFaceTracker


def test_second_person_motion_away_from_skip_zone():
    """skip ゾーン外の motion は 2 人目。"""
    skip_zone = (200, 100, 400, 300)
    motion = MotionEvent(
        detected=True,
        bbox=(520, 380, 80, 80),
        bboxes=[(520, 380, 80, 80)],
        area=6400,
    )
    assert has_second_person_motion(motion, skip_zone, owner_margin=0.8) is True


def test_skip_user_motion_near_zone():
    """skip ユーザー付近の motion のみ → 2 人目ではない。"""
    skip_zone = (200, 100, 400, 300)
    motion = MotionEvent(
        detected=True,
        bbox=(250, 150, 80, 80),
        bboxes=[(250, 150, 80, 80)],
        area=6400,
    )
    assert has_second_person_motion(motion, skip_zone, owner_margin=0.8) is False


def test_two_blobs_one_away_means_second_person():
    """blob が2つで1つが skip 外 → 2 人目。"""
    skip_zone = (200, 100, 400, 300)
    motion = MotionEvent(
        detected=True,
        bbox=(520, 380, 80, 80),
        bboxes=[(250, 150, 80, 80), (520, 380, 80, 80)],
        area=6400,
    )
    assert has_second_person_motion(motion, skip_zone, owner_margin=0.8) is True


def test_face_in_out_with_grace(tmp_path):
    """顔 in/out 時も skip ゾーン内 motion は minimize しない。"""
    config = Config()
    config.faces_skip_data_dir = tmp_path / "skip"
    config.faces_kill_data_dir = tmp_path / "kill"
    service = FaceRecognitionService(config, flow="skip")
    service.register_user("sanhdp", np.random.rand(128), source="webcam")

    tracker = SkipFaceTracker(grace_seconds=4.0)
    skip_zone = (200, 100, 400, 300)
    tracker.update(skip_zone, now=10.0)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    motion = MotionEvent(
        detected=True,
        bbox=(250, 150, 80, 80),
        bboxes=[(250, 150, 80, 80)],
        area=6400,
    )

    assert should_skip_motion_minimize(
        service,
        frame,
        motion,
        tracker,
        now=12.0,
        owner_margin=0.8,
        motion_overlap_ratio=0.25,
    ) is True


def test_no_recent_skip_zone_means_minimize(tmp_path):
    """猶予外で skip ゾーンなし → minimize。"""
    config = Config()
    config.faces_skip_data_dir = tmp_path / "skip"
    config.faces_kill_data_dir = tmp_path / "kill"
    service = FaceRecognitionService(config, flow="skip")
    service.register_user("sanhdp", np.random.rand(128), source="webcam")

    tracker = SkipFaceTracker(grace_seconds=2.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    motion = MotionEvent(
        detected=True,
        bbox=(250, 150, 80, 80),
        bboxes=[(250, 150, 80, 80)],
        area=6400,
    )

    assert should_skip_motion_minimize(
        service,
        frame,
        motion,
        tracker,
        now=10.0,
        owner_margin=0.8,
        motion_overlap_ratio=0.25,
    ) is False
