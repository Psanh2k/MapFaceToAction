"""カメラフレームの動体検知。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.config import Config
from src.logger import setup_logger

MotionBBox = Tuple[int, int, int, int]


@dataclass
class MotionEvent:
    """動体検知結果。"""

    detected: bool
    bbox: Optional[MotionBBox] = None
    bboxes: List[MotionBBox] = field(default_factory=list)
    area: float = 0.0


class MotionDetector:
    """フレーム差分による簡易動体検知。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._prev_gray: Optional[np.ndarray] = None
        self._warmup_frames = 0
        self._scale_x = 1.0
        self._scale_y = 1.0

    def reset(self) -> None:
        """背景状態をリセットする。"""
        self._prev_gray = None
        self._warmup_frames = 0

    def _to_gray_small(self, frame: np.ndarray) -> np.ndarray:
        """処理負荷軽減のため縮小グレースケールに変換する。"""
        height, width = frame.shape[:2]
        target_width = self._config.motion_frame_width
        if width > target_width:
            scale = target_width / width
            small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
            self._scale_x = width / small.shape[1]
            self._scale_y = height / small.shape[0]
        else:
            small = frame
            self._scale_x = 1.0
            self._scale_y = 1.0

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blur = self._config.motion_blur_size
        if blur % 2 == 0:
            blur += 1
        return cv2.GaussianBlur(gray, (blur, blur), 0)

    def _to_full_frame_bbox(self, x: int, y: int, w: int, h: int) -> MotionBBox:
        """縮小座標を元フレーム座標へ変換する。"""
        return (
            int(x * self._scale_x),
            int(y * self._scale_y),
            int(w * self._scale_x),
            int(h * self._scale_y),
        )

    def detect_event(self, frame: np.ndarray) -> MotionEvent:
        """動体検知結果（位置付き）を返す。"""
        gray = self._to_gray_small(frame)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._warmup_frames += 1
            return MotionEvent(detected=False)

        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        _, thresh = cv2.threshold(
            diff,
            self._config.motion_threshold,
            255,
            cv2.THRESH_BINARY,
        )
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        motion_bboxes: List[MotionBBox] = []
        best_area = 0.0
        best_bbox: Optional[MotionBBox] = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self._config.motion_min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            full_bbox = self._to_full_frame_bbox(x, y, w, h)
            motion_bboxes.append(full_bbox)
            if area > best_area:
                best_area = area
                best_bbox = full_bbox

        if best_bbox is not None:
            self._logger.debug(
                "Motion detected (area=%.0f, blobs=%d, bbox=%s)",
                best_area,
                len(motion_bboxes),
                best_bbox,
            )
            return MotionEvent(
                detected=True,
                bbox=best_bbox,
                bboxes=motion_bboxes,
                area=best_area,
            )

        return MotionEvent(detected=False)

    def detect(self, frame: np.ndarray) -> bool:
        """動体を検知したら True。"""
        return self.detect_event(frame).detected
