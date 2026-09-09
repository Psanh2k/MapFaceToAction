"""skip ユーザー向け minimize 判定。"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from src.face_recognition_service import FaceRecognitionService
from src.motion_detector import MotionBBox, MotionEvent

FaceBBox = Tuple[int, int, int, int]


def _expand_face_bbox(
    left: int, top: int, right: int, bottom: int, margin_ratio: float
) -> FaceBBox:
    """顔 bbox を拡張する（left, top, right, bottom）。"""
    width = max(right - left, 1)
    height = max(bottom - top, 1)
    pad_x = int(width * margin_ratio)
    pad_y = int(height * margin_ratio)
    return (
        left - pad_x,
        top - pad_y,
        right + pad_x,
        bottom + pad_y,
    )


def _bbox_intersection_area(a: FaceBBox, b: MotionBBox) -> float:
    """2 bbox の交差面積。"""
    ax1, ay1, ax2, ay2 = a[0], a[1], a[2], a[3]
    bx, by, bw, bh = b
    bx2, by2 = bx + bw, by + bh

    ix1 = max(ax1, bx)
    iy1 = max(ay1, by)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return float((ix2 - ix1) * (iy2 - iy1))


def motion_near_skip_face(
    motion: MotionEvent,
    face_bbox: FaceBBox,
    margin_ratio: float,
    overlap_ratio: float,
) -> bool:
    """動体が skip ユーザーの顔付近か。"""
    if not motion.detected or motion.bbox is None:
        return False

    expanded = _expand_face_bbox(*face_bbox, margin_ratio)
    motion_area = max(motion.bbox[2] * motion.bbox[3], 1)
    overlap = _bbox_intersection_area(expanded, motion.bbox)
    if overlap / motion_area >= overlap_ratio:
        return True

    mx = motion.bbox[0] + motion.bbox[2] / 2
    my = motion.bbox[1] + motion.bbox[3] / 2
    left, top, right, bottom = expanded
    return left <= mx <= right and top <= my <= bottom


def should_skip_motion_minimize(
    skip_service: FaceRecognitionService,
    frame: np.ndarray,
    motion: MotionEvent,
    face_margin_ratio: float,
    motion_overlap_ratio: float,
) -> bool:
    """
    minimize をスキップするか。

    - skip ユーザー不在 → スキップしない（minimize する）
    - 動体が skip 顔付近 → スキップする
    - 動体が skip 顔の外（他人の通過など）→ スキップしない
    """
    if not skip_service.is_loaded:
        return False

    face_bbox = skip_service.get_primary_skip_face_bbox(frame)
    if face_bbox is None:
        return False

    return motion_near_skip_face(
        motion,
        face_bbox,
        margin_ratio=face_margin_ratio,
        overlap_ratio=motion_overlap_ratio,
    )
