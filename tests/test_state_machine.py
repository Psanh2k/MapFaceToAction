"""状態マシンのテスト。"""

import time
from unittest.mock import MagicMock

from src.config import Config
from src.state_machine import AppState, StateMachine


def _make_config(**overrides) -> Config:
    """テスト用 Config を生成する。"""
    config = Config()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_no_face_no_trigger():
    """Test 1: 顔なし → トリガーなし。"""
    config = _make_config(required_match_seconds=1.0)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=0, is_match=False)
    assert sm.state == AppState.NO_FACE
    callback.assert_not_called()


def test_unknown_face_no_trigger():
    """Test 2: 未知の顔 → トリガーなし。"""
    config = _make_config(required_match_seconds=1.0)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=1, is_match=False)
    assert sm.state == AppState.FACE_DETECTED
    callback.assert_not_called()


def test_brief_match_no_trigger():
    """Test 3: 登録顔が一瞬 → トリガーなし。"""
    config = _make_config(required_match_seconds=2.0, match_reset_grace_ms=0)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=1, is_match=True)
    assert sm.state == AppState.MATCHING
    sm.update(face_count=0, is_match=False)
    assert sm.state == AppState.NO_FACE
    callback.assert_not_called()


def test_match_grace_allows_brief_miss():
    """短い不一致は猶予内ならタイマーを維持する。"""
    config = _make_config(
        required_match_seconds=0.5,
        match_reset_grace_ms=500,
    )
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=1, is_match=True)
    sm.update(face_count=1, is_match=False)
    assert sm.state == AppState.MATCHING
    time.sleep(0.6)
    sm.update(face_count=1, is_match=True)
    callback.assert_called_once()


def test_continuous_match_triggers():
    """Test 4: 連続マッチ → トリガー。"""
    config = _make_config(required_match_seconds=0.5)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=1, is_match=True)
    time.sleep(0.6)
    sm.update(face_count=1, is_match=True)

    assert sm.state == AppState.TRIGGERED
    callback.assert_called_once()


def test_multiple_faces_no_trigger():
    """Test 5: 複数顔 → トリガーなし。"""
    config = _make_config(required_match_seconds=0.5, require_single_face=True)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=2, is_match=True)
    assert sm.state == AppState.NO_FACE
    callback.assert_not_called()


def test_cooldown_prevents_retrigger():
    """Test 7: トリガー後クールダウン中は再トリガーしない。"""
    config = _make_config(required_match_seconds=0.1, trigger_cooldown_seconds=10.0)
    sm = StateMachine(config)
    callback = MagicMock()
    sm.set_trigger_callback(callback)

    sm.update(face_count=1, is_match=True)
    time.sleep(0.2)
    sm.update(face_count=1, is_match=True)
    assert callback.call_count == 1

    sm._transition(AppState.TRIGGERED)
    sm._start_cooldown()
    sm.update(face_count=1, is_match=True)
    assert callback.call_count == 1
