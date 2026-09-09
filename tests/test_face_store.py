"""FaceStore のテスト。"""

import numpy as np
import pytest

from src.face_store import FaceStore, sanitize_user_name


def test_sanitize_user_name():
    """ユーザー名正規化。"""
    assert sanitize_user_name("Alice") == "alice"
    assert sanitize_user_name("john_doe") == "john_doe"
    assert sanitize_user_name("  Mary-Jane  ") == "mary-jane"


def test_sanitize_invalid_name():
    """無効なユーザー名。"""
    with pytest.raises(ValueError):
        sanitize_user_name("   ")


def test_save_load_delete_user(tmp_path):
    """保存・読み込み・削除。"""
    store = FaceStore(tmp_path / "faces")
    encoding = np.random.rand(128)

    path = store.save("alice", encoding, source="image")
    assert path.exists()

    users = store.load_all()
    assert "alice" in users
    np.testing.assert_array_almost_equal(users["alice"].encoding, encoding)

    assert store.list_users() == ["alice"]
    assert store.delete("alice") is True
    assert store.list_users() == []


def test_migrate_legacy(tmp_path):
    """旧 face_encoding.pkl から default へ移行。"""
    import pickle

    legacy = tmp_path / "face_encoding.pkl"
    encoding = np.random.rand(128)
    with open(legacy, "wb") as fh:
        pickle.dump({"encoding": encoding.tolist()}, fh)

    store = FaceStore(tmp_path / "faces", legacy_path=legacy)
    users = store.load_all()
    assert "default" in users
    assert store.list_users() == ["default"]
