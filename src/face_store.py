"""複数ユーザーの顔エンコーディング永続化。"""

from __future__ import annotations

import os
import pickle
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


def sanitize_user_name(name: str) -> str:
    """ユーザー名を安全なファイル名に正規化する。"""
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or len(cleaned) > 64:
        raise ValueError(f"Invalid user name: {name!r}")
    return cleaned


@dataclass
class RegisteredFace:
    """登録済みユーザー情報。"""

    name: str
    encoding: np.ndarray
    source: str


class FaceStore:
    """data/faces/ 以下のマルチユーザーデータ管理。"""

    def __init__(self, faces_dir: Path, legacy_path: Optional[Path] = None) -> None:
        self._faces_dir = faces_dir
        self._legacy_path = legacy_path

    @property
    def faces_dir(self) -> Path:
        return self._faces_dir

    def user_file_path(self, name: str) -> Path:
        """ユーザー名に対応する保存パス。"""
        safe_name = sanitize_user_name(name)
        return self._faces_dir / f"{safe_name}.pkl"

    def save(self, name: str, encoding: np.ndarray, source: str) -> Path:
        """ユーザーの顔エンコーディングを保存する。"""
        safe_name = sanitize_user_name(name)
        self._faces_dir.mkdir(parents=True, exist_ok=True)
        path = self._faces_dir / f"{safe_name}.pkl"
        data = {
            "name": safe_name,
            "encoding": encoding.tolist(),
            "source": source,
        }
        with open(path, "wb") as fh:
            pickle.dump(data, fh)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        try:
            os.chmod(self._faces_dir, 0o700)
        except OSError:
            pass
        return path

    def delete(self, name: str) -> bool:
        """ユーザーを削除する。"""
        path = self.user_file_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_users(self) -> List[str]:
        """登録済みユーザー名一覧。"""
        self.migrate_legacy_if_needed()
        if not self._faces_dir.exists():
            return []
        return sorted(p.stem for p in self._faces_dir.glob("*.pkl"))

    def migrate_root_pkls_if_needed(self) -> None:
        """旧 data/faces/*.pkl を kill サブディレクトリへ移行する。"""
        if self._faces_dir.name != "kill":
            return

        parent = self._faces_dir.parent
        if not parent.exists():
            return

        self._faces_dir.mkdir(parents=True, exist_ok=True)
        for path in parent.glob("*.pkl"):
            target = self._faces_dir / path.name
            if target.exists():
                continue
            shutil.move(str(path), str(target))

    def load_all(self) -> Dict[str, RegisteredFace]:
        """全登録ユーザーを読み込む。"""
        self.migrate_legacy_if_needed()
        self.migrate_root_pkls_if_needed()
        users: Dict[str, RegisteredFace] = {}
        if not self._faces_dir.exists():
            return users

        for path in self._faces_dir.glob("*.pkl"):
            with open(path, "rb") as fh:
                data = pickle.load(fh)
            user_name = data.get("name", path.stem)
            users[user_name] = RegisteredFace(
                name=user_name,
                encoding=np.array(data["encoding"]),
                source=data.get("source", "unknown"),
            )
        return users

    def migrate_legacy_if_needed(self) -> None:
        """旧 face_encoding.pkl を default ユーザーとして移行する。"""
        if self._legacy_path is None or not self._legacy_path.exists():
            return

        self._faces_dir.mkdir(parents=True, exist_ok=True)
        if any(self._faces_dir.glob("*.pkl")):
            return

        with open(self._legacy_path, "rb") as fh:
            data = pickle.load(fh)

        if isinstance(data, dict) and "encoding" in data:
            encoding = np.array(data["encoding"])
        elif isinstance(data, np.ndarray):
            encoding = data
        else:
            return

        self.save("default", encoding, "legacy")
