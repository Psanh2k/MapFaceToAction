"""カメラフレームの動体検知。"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from src.config import Config
from src.logger import setup_logger


class MotionDetector:
    """フレーム差分による簡易動体検知。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._prev_gray: Optional[np.ndarray] = None
        self._warmup_frames = 0

    def reset(self) -> None:
        """背景状態をリセットする。"""
        self._prev_gray = None
        self._warmup_frames = 0

    def _to_gray_small(self, frame: np.ndarray) -> np.ndarray:
        """処理負荷軽減のため縮小グレースケールに変換。"""
        height, width = frame.shape[:2]
        target_width = self._config.motion_frame_width
        if width > target_width:
            scale = target_width / width
            frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = self._config.motion_blur_size
        if blur % 2 == 0:
            blur += 1
        return cv2.GaussianBlur(gray, (blur, blur), 0)

    def detect(self, frame: np.ndarray) -> bool:
        """動体を検知したら True。"""
        gray = self._to_gray_small(frame)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._warmup_frames += 1
            return False

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

        for contour in contours:
            if cv2.contourArea(contour) >= self._config.motion_min_area:
                self._logger.debug(
                    "Motion detected (area=%.0f)",
                    cv2.contourArea(contour),
                )
                return True

        return False
