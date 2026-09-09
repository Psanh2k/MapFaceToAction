"""動体検知のテスト。"""

import numpy as np

from src.config import Config
from src.motion_detector import MotionDetector


def test_no_motion_on_static_frame():
    """静止フレームでは動体なし。"""
    config = Config()
    config.motion_threshold = 25
    config.motion_min_area = 500
    detector = MotionDetector(config)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert detector.detect(frame) is False
    assert detector.detect(frame) is False


def test_motion_on_changed_frame():
    """大きな変化で動体検知。"""
    config = Config()
    config.motion_threshold = 10
    config.motion_min_area = 100
    config.motion_frame_width = 640
    detector = MotionDetector(config)

    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2 = frame1.copy()
    cv2 = __import__("cv2")
    cv2.rectangle(frame2, (100, 100), (400, 400), (255, 255, 255), -1)

    event1 = detector.detect_event(frame1)
    assert event1.detected is False

    event2 = detector.detect_event(frame2)
    assert event2.detected is True
    assert event2.bbox is not None
