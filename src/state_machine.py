"""顔認識結果に基づく状態遷移管理。"""

from __future__ import annotations

import enum
import time
from typing import Callable, Optional

from src.config import Config
from src.logger import setup_logger


class AppState(enum.Enum):
    """アプリケーション状態。"""

    NO_FACE = "NO_FACE"
    FACE_DETECTED = "FACE_DETECTED"
    MATCHING = "MATCHING"
    TRIGGERED = "TRIGGERED"
    COOLDOWN = "COOLDOWN"
    ERROR = "ERROR"


class StateMachine:
    """連続マッチ検証とクールダウンを管理する状態マシン。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._state = AppState.NO_FACE
        self._match_start_time: Optional[float] = None
        self._last_match_time: Optional[float] = None
        self._cooldown_start_time: Optional[float] = None
        self._on_trigger: Optional[Callable[[], None]] = None
        self._retrigger_armed: bool = True
        self._face_absent_since: Optional[float] = None

    @property
    def state(self) -> AppState:
        """現在の状態。"""
        return self._state

    def set_trigger_callback(self, callback: Callable[[], None]) -> None:
        """トリガー発火時のコールバックを設定する。"""
        self._on_trigger = callback

    def _transition(self, new_state: AppState) -> None:
        """状態遷移を行いログ出力する。"""
        if self._state != new_state:
            self._logger.debug("State: %s -> %s", self._state.value, new_state.value)
            self._state = new_state

    def _reset_match_timer(self) -> None:
        """マッチタイマーをリセットする。"""
        self._match_start_time = None
        self._last_match_time = None

    def _within_match_grace(self, now: float) -> bool:
        """直近マッチから猶予時間内か。"""
        if self._last_match_time is None:
            return False
        return (now - self._last_match_time) <= self._config.match_reset_grace_seconds

    def _update_retrigger_arm(self, face_count: int, now: float) -> None:
        """再トリガー前に顔がフレーム外にあることを要求する。"""
        if not self._config.require_face_absence_before_retrigger:
            self._retrigger_armed = True
            return

        if self._retrigger_armed:
            return

        if face_count == 0:
            if self._face_absent_since is None:
                self._face_absent_since = now
            elif now - self._face_absent_since >= self._config.face_absence_seconds:
                self._retrigger_armed = True
                self._face_absent_since = None
                self._logger.info(
                    "Face absent for %.0fs - ready for next service trigger",
                    self._config.face_absence_seconds,
                )
        else:
            self._face_absent_since = None

    def update(self, face_count: int, is_match: bool) -> None:
        """顔検出結果に基づいて状態を更新する。"""
        now = time.monotonic()
        self._update_retrigger_arm(face_count, now)

        # クールダウン中は処理をスキップ
        if self._state == AppState.COOLDOWN:
            if self._cooldown_start_time is not None:
                elapsed = time.monotonic() - self._cooldown_start_time
                if elapsed >= self._config.trigger_cooldown_seconds:
                    self._logger.info("Cooldown finished, resuming monitoring")
                    self._cooldown_start_time = None
                    self._reset_match_timer()
                    self._transition(AppState.NO_FACE)
                    if self._config.require_face_absence_before_retrigger:
                        self._retrigger_armed = False
                        self._face_absent_since = None
                        self._logger.info(
                            "Move face away from camera before next trigger can occur"
                        )
                else:
                    return
            else:
                self._transition(AppState.NO_FACE)
            return

        # 再トリガー待機中（サービス起因 kill の後）
        if not self._retrigger_armed:
            return

        # トリガー済み → クールダウンへ
        if self._state == AppState.TRIGGERED:
            self._start_cooldown()
            return

        # 複数顔 → リセット
        if self._config.require_single_face and face_count > 1:
            self._logger.debug("Multiple faces detected, resetting")
            self._reset_match_timer()
            self._transition(AppState.NO_FACE)
            return

        # 顔なし
        if face_count == 0:
            if self._state == AppState.MATCHING and self._within_match_grace(now):
                self._logger.debug("Face briefly lost, within grace period")
                return
            if self._state in (AppState.MATCHING, AppState.FACE_DETECTED):
                self._logger.debug("Face lost, resetting match timer")
            self._reset_match_timer()
            self._transition(AppState.NO_FACE)
            return

        # 1顔だが不一致
        if not is_match:
            if self._state == AppState.MATCHING and self._within_match_grace(now):
                self._logger.debug("Face briefly unmatched, within grace period")
                return
            if self._state == AppState.MATCHING:
                self._logger.debug("Face no longer matches, resetting")
            self._reset_match_timer()
            self._transition(AppState.FACE_DETECTED)
            return

        # 1顔で一致
        self._last_match_time = now
        if self._match_start_time is None:
            self._match_start_time = now
            self._logger.info("Face match started")
            self._transition(AppState.MATCHING)
            return

        elapsed = now - self._match_start_time
        if elapsed >= self._config.required_match_seconds:
            self._logger.info("Face match confirmed (%.1fs)", elapsed)
            self._transition(AppState.TRIGGERED)
            self._fire_trigger()
        else:
            self._transition(AppState.MATCHING)

    def _fire_trigger(self) -> None:
        """トリガーコールバックを実行する。"""
        self._retrigger_armed = False
        self._face_absent_since = None
        if self._on_trigger is not None:
            self._on_trigger()

    def _start_cooldown(self) -> None:
        """クールダウン状態に入る。"""
        self._cooldown_start_time = time.monotonic()
        self._reset_match_timer()
        self._transition(AppState.COOLDOWN)
        self._logger.info(
            "Entering cooldown for %.0fs",
            self._config.trigger_cooldown_seconds,
        )

    def reset(self) -> None:
        """状態マシンを初期状態にリセットする。"""
        self._reset_match_timer()
        self._cooldown_start_time = None
        self._retrigger_armed = True
        self._face_absent_since = None
        self._transition(AppState.NO_FACE)
