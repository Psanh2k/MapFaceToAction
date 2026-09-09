"""skip ユーザーの顔位置を短期記憶する。"""

from __future__ import annotations

from typing import Optional, Tuple

FaceBBox = Tuple[int, int, int, int]


class SkipFaceTracker:
    """顔 in/out 時も skip ゾーンを維持する。"""

    def __init__(self, grace_seconds: float) -> None:
        self._grace_seconds = grace_seconds
        self._last_bbox: Optional[FaceBBox] = None
        self._last_seen: Optional[float] = None

    def update(self, face_bbox: Optional[FaceBBox], now: float) -> None:
        """skip 顔 bbox を更新する。"""
        if face_bbox is None:
            return
        self._last_bbox = face_bbox
        self._last_seen = now

    def get_active_zone(self, now: float) -> Optional[FaceBBox]:
        """現在有効な skip ゾーン（猶予内）。"""
        if self._last_bbox is None or self._last_seen is None:
            return None
        if (now - self._last_seen) > self._grace_seconds:
            return None
        return self._last_bbox

    def reset(self) -> None:
        """状態をリセットする。"""
        self._last_bbox = None
        self._last_seen = None
