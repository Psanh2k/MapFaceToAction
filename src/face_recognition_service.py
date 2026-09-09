"""顔検出・エンコーディング・照合サービス。"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import face_recognition
import numpy as np

from src.config import Config
from src.face_store import FaceStore, sanitize_user_name
from src.logger import setup_logger


class FaceRecognitionService:
    """face_recognition ライブラリをラップするサービス。"""

    # フレームリサイズ倍率（CPU負荷軽減）
    RESIZE_FACTOR = 0.25
    # 登録時の最小顔サイズ（ピクセル）
    MIN_FACE_SIZE = 80

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._store = FaceStore(
            config.faces_data_absolute_dir,
            legacy_path=config.face_encoding_absolute_path,
        )
        self._registered_users: Dict[str, np.ndarray] = {}
        self._last_matched_user: Optional[str] = None

    @property
    def last_matched_user(self) -> Optional[str]:
        """直近フレームで一致したユーザー名。"""
        return self._last_matched_user

    @property
    def registered_user_names(self) -> List[str]:
        """登録済みユーザー名一覧。"""
        return sorted(self._registered_users.keys())

    def load_registered_faces(self) -> None:
        """全登録ユーザーを読み込む。"""
        users = self._store.load_all()
        if not users:
            raise FileNotFoundError(
                f"No registered faces in {self._store.faces_dir}. "
                "Run: python register.py <name>"
            )

        self._registered_users = {
            name: user.encoding for name, user in users.items()
        }
        self._logger.info(
            "Loaded %d registered user(s): %s",
            len(self._registered_users),
            ", ".join(self.registered_user_names),
        )

    def load_registered_face(self) -> None:
        """後方互換: load_registered_faces のエイリアス。"""
        self.load_registered_faces()

    @property
    def is_loaded(self) -> bool:
        """登録済み顔が読み込まれているか。"""
        return len(self._registered_users) > 0

    def list_users(self) -> List[str]:
        """登録済みユーザー一覧（ディスクから）。"""
        return self._store.list_users()

    def delete_user(self, name: str) -> bool:
        """ユーザーを削除する。"""
        safe_name = sanitize_user_name(name)
        deleted = self._store.delete(safe_name)
        if deleted:
            self._registered_users.pop(safe_name, None)
            self._logger.info("Deleted user: %s", safe_name)
        return deleted

    def register_user(
        self,
        name: str,
        encoding: np.ndarray,
        source: str,
    ) -> Path:
        """ユーザーを登録または上書きする。"""
        safe_name = sanitize_user_name(name)
        path = self._store.save(safe_name, encoding, source)
        self._registered_users[safe_name] = encoding
        self._logger.info("Registered user '%s' from %s -> %s", safe_name, source, path)
        return path

    def _prepare_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """BGR→RGB変換とリサイズを行う。"""
        small_frame = cv2.resize(
            frame,
            (0, 0),
            fx=self.RESIZE_FACTOR,
            fy=self.RESIZE_FACTOR,
        )
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        return rgb_frame, 1.0 / self.RESIZE_FACTOR

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """フレーム内の顔位置 (top, right, bottom, left) を返す。"""
        rgb_frame, _ = self._prepare_frame(frame)
        locations = face_recognition.face_locations(rgb_frame, model="hog")
        return locations

    def encode_faces(
        self,
        frame: np.ndarray,
        locations: List[Tuple[int, int, int, int]],
        rgb_frame: Optional[np.ndarray] = None,
        num_jitters: int = 0,
    ) -> List[np.ndarray]:
        """指定位置の顔エンコーディングを生成する。"""
        if not locations:
            return []
        if rgb_frame is None:
            rgb_frame, _ = self._prepare_frame(frame)
        encodings = face_recognition.face_encodings(
            rgb_frame, locations, num_jitters=num_jitters
        )
        return encodings

    def find_matching_user(self, encoding: np.ndarray) -> Optional[str]:
        """登録ユーザー中で最も近い一致ユーザーを返す。"""
        if not self._registered_users:
            raise RuntimeError("Registered faces not loaded")

        best_name: Optional[str] = None
        best_distance = float("inf")

        for name, known_encoding in self._registered_users.items():
            distance = face_recognition.face_distance([known_encoding], encoding)[0]
            self._logger.debug(
                "Face distance vs %s: %.4f (threshold: %.2f)",
                name,
                distance,
                self._config.face_match_threshold,
            )
            if distance <= self._config.face_match_threshold and distance < best_distance:
                best_distance = distance
                best_name = name

        return best_name

    def is_match(self, encoding: np.ndarray) -> bool:
        """いずれかの登録ユーザーと一致するか。"""
        matched = self.find_matching_user(encoding)
        self._last_matched_user = matched
        return matched is not None

    def register_from_image_file(
        self,
        image_path: Path,
        user_name: str,
        num_jitters: int = 1,
    ) -> Path:
        """画像ファイルからユーザーを登録する。"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        image = face_recognition.load_image_file(str(path))
        locations = face_recognition.face_locations(image, model="hog")
        face_count = len(locations)

        if face_count == 0:
            raise ValueError("No face found in image")
        if face_count > 1:
            raise ValueError(
                f"Multiple faces found ({face_count}). Use a photo with one person."
            )

        encodings = face_recognition.face_encodings(
            image, locations, num_jitters=num_jitters
        )
        if not encodings:
            raise ValueError("Could not encode face from image")

        save_path = self.register_user(user_name, encodings[0], source="image")
        self._logger.info("Registered face from image: %s", path)
        return save_path

    def save_encoding(self, encoding: np.ndarray, path: Optional[Path] = None) -> Path:
        """後方互換: default ユーザーとして保存。"""
        if path is not None:
            save_path = path
            save_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"encoding": encoding.tolist()}
            with open(save_path, "wb") as fh:
                pickle.dump(data, fh)
            try:
                os.chmod(save_path, 0o600)
            except OSError:
                pass
            return save_path
        return self.register_user("default", encoding, source="webcam")

    def validate_sample_consistency(self, encodings: List[np.ndarray]) -> bool:
        """複数サンプルの一貫性を検証する。"""
        if len(encodings) < 2:
            return True

        reference = encodings[0]
        for enc in encodings[1:]:
            distance = face_recognition.face_distance([reference], enc)[0]
            if distance > self._config.face_match_threshold:
                self._logger.warning(
                    "Inconsistent sample detected (distance: %.4f)", distance
                )
                return False
        return True

    def compute_average_encoding(self, encodings: List[np.ndarray]) -> np.ndarray:
        """複数エンコーディングの平均を計算する。"""
        return np.mean(encodings, axis=0)

    def is_face_large_enough(
        self, location: Tuple[int, int, int, int], scale: float
    ) -> bool:
        """顔が十分な大きさか判定する。"""
        top, right, bottom, left = location
        width = (right - left) * scale
        height = (bottom - top) * scale
        return width >= self.MIN_FACE_SIZE and height >= self.MIN_FACE_SIZE

    def analyze_frame(
        self, frame: np.ndarray
    ) -> Tuple[int, bool, Optional[np.ndarray], Optional[str]]:
        """フレームを解析し (顔数, 一致, エンコーディング, ユーザー名) を返す。"""
        rgb_frame, _ = self._prepare_frame(frame)
        locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_count = len(locations)

        if face_count == 0:
            self._last_matched_user = None
            return 0, False, None, None

        if self._config.require_single_face and face_count > 1:
            self._last_matched_user = None
            return face_count, False, None, None

        encodings = self.encode_faces(frame, locations, rgb_frame=rgb_frame)
        if not encodings:
            self._last_matched_user = None
            return face_count, False, None, None

        matched_user = self.find_matching_user(encodings[0])
        self._last_matched_user = matched_user
        return face_count, matched_user is not None, encodings[0], matched_user
