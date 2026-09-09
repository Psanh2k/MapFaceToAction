"""顔検出・エンコーディング・照合サービス。"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import face_recognition
import numpy as np

from src.config import Config
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
        self._registered_encoding: Optional[np.ndarray] = None

    def load_registered_face(self) -> None:
        """登録済み顔エンコーディングを読み込む。"""
        path = self._config.face_encoding_absolute_path
        if not path.exists():
            raise FileNotFoundError(
                f"Face encoding not found at {path}. Run register.py first."
            )

        with open(path, "rb") as fh:
            data = pickle.load(fh)

        if isinstance(data, dict) and "encoding" in data:
            self._registered_encoding = np.array(data["encoding"])
        elif isinstance(data, np.ndarray):
            self._registered_encoding = data
        else:
            raise ValueError("Invalid face encoding file format")

        # ファイル権限をユーザー専用に制限
        try:
            os.chmod(path, 0o600)
        except OSError:
            self._logger.warning("Could not set permissions on %s", path)

        self._logger.info("Registered face loaded from %s", path)

    @property
    def is_loaded(self) -> bool:
        """登録済み顔が読み込まれているか。"""
        return self._registered_encoding is not None

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
    ) -> List[np.ndarray]:
        """指定位置の顔エンコーディングを生成する。"""
        if not locations:
            return []
        rgb_frame, _ = self._prepare_frame(frame)
        encodings = face_recognition.face_encodings(rgb_frame, locations)
        return encodings

    def is_match(self, encoding: np.ndarray) -> bool:
        """登録済み顔と一致するか判定する。"""
        if self._registered_encoding is None:
            raise RuntimeError("Registered face not loaded")

        distance = face_recognition.face_distance(
            [self._registered_encoding], encoding
        )[0]
        matched = distance <= self._config.face_match_threshold
        self._logger.debug("Face distance: %.4f (threshold: %.2f)", distance, self._config.face_match_threshold)
        return bool(matched)

    def save_encoding(self, encoding: np.ndarray, path: Optional[Path] = None) -> Path:
        """顔エンコーディングを保存する。"""
        save_path = path or self._config.face_encoding_absolute_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"encoding": encoding.tolist()}
        with open(save_path, "wb") as fh:
            pickle.dump(data, fh)

        try:
            os.chmod(save_path, 0o600)
        except OSError:
            self._logger.warning("Could not set permissions on %s", save_path)

        self._registered_encoding = encoding
        self._logger.info("Face encoding saved to %s", save_path)
        return save_path

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
    ) -> Tuple[int, bool, Optional[np.ndarray]]:
        """フレームを解析し (顔数, 一致, エンコーディング) を返す。"""
        locations = self.detect_faces(frame)
        face_count = len(locations)

        if face_count == 0:
            return 0, False, None

        if self._config.require_single_face and face_count > 1:
            return face_count, False, None

        encodings = self.encode_faces(frame, locations)
        if not encodings:
            return face_count, False, None

        matched = self.is_match(encodings[0])
        return face_count, matched, encodings[0]
