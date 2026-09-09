"""skip フロー向けの顔プレゼンス追跡。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.face_recognition_service import FaceRecognitionService


class SkipPresenceTracker:
    """直近で他人・複数人が映ったかを記録する。"""

    def __init__(self, grace_seconds: float) -> None:
        self._grace_seconds = grace_seconds
        self._last_stranger_time: Optional[float] = None

    def update(self, skip_service: "FaceRecognitionService", frame, now: Optional[float] = None) -> None:
        """フレームを解析し、他人検出時刻を更新する。"""
        if not skip_service.is_loaded:
            return

        timestamp = time.monotonic() if now is None else now
        face_count, skip_count, stranger_count = skip_service.count_skip_presence(frame)

        # 複数人または未登録の顔があれば他人扱い
        if stranger_count > 0 or face_count >= 2:
            self._last_stranger_time = timestamp

    def stranger_recently_present(self, now: Optional[float] = None) -> bool:
        """猶予期間内に他人が映っていたか。"""
        if self._last_stranger_time is None:
            return False
        timestamp = time.monotonic() if now is None else now
        return (timestamp - self._last_stranger_time) <= self._grace_seconds

    def reset(self) -> None:
        """状態をリセットする。"""
        self._last_stranger_time = None
