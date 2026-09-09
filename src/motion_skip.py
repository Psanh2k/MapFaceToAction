"""skip ユーザー向け minimize 判定。"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from src.face_recognition_service import FaceRecognitionService
from src.motion_detector import MotionBBox, MotionEvent
from src.skip_face_tracker import SkipFaceTracker

FaceBBox = Tuple[int, int, int, int]


def _motion_center(blob: MotionBBox) -> Tuple[float, float]:
    """motion blob の中心。"""
    return blob[0] + blob[2] / 2, blob[1] + blob[3] / 2


def _is_skip_user_motion_blob(
    blob: MotionBBox,
    skip_zone: FaceBBox,
    owner_margin: float,
) -> bool:
    """
    skip ユーザー自身の motion か。

    顔中心からの距離が owner ゾーン内なら skip ユーザーの動き。
    """
    left, top, right, bottom = skip_zone
    face_cx = (left + right) / 2
    face_cy = (top + bottom) / 2
    face_size = max(right - left, bottom - top, 1)
    cx, cy = _motion_center(blob)
    dist = math.hypot(cx - face_cx, cy - face_cy)
    return dist <= face_size * (0.5 + owner_margin)


def _motion_blobs(motion: MotionEvent) -> List[MotionBBox]:
    """検知された全 motion blob。"""
    if motion.bboxes:
        return motion.bboxes
    if motion.bbox is not None:
        return [motion.bbox]
    return []


def has_second_person_motion(
    motion: MotionEvent,
    skip_zone: FaceBBox,
    owner_margin: float,
) -> bool:
    """
    2人目の motion があるか（顔検出不要）。

    いずれかの blob が skip ユーザーの owner ゾーン外なら True。
    """
    blobs = _motion_blobs(motion)
    if not blobs:
        return False

    return any(
        not _is_skip_user_motion_blob(blob, skip_zone, owner_margin)
        for blob in blobs
    )


def should_skip_motion_minimize(
    skip_service: FaceRecognitionService,
    frame: np.ndarray,
    motion: MotionEvent,
    tracker: SkipFaceTracker,
    now: float,
    owner_margin: float,
    motion_overlap_ratio: float,
) -> bool:
    """
    minimize をスキップするか。

    - skip ユーザーの motion のみ → True
    - 2人目の motion → False
    """
    del motion_overlap_ratio  # 距離ベース判定に統一

    if not skip_service.is_loaded or not motion.detected:
        return False

    current_bbox = skip_service.get_primary_skip_face_bbox(frame)
    tracker.update(current_bbox, now)
    skip_zone = tracker.get_active_zone(now)

    if skip_zone is None:
        return False

    if has_second_person_motion(motion, skip_zone, owner_margin):
        return False

    return True
