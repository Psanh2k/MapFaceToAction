"""Webカメラのキャプチャとエラーハンドリング。"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.config import Config
from src.logger import setup_logger


class CameraError(Exception):
    """カメラ関連のエラー。"""


class Camera:
    """Webカメラを開き、フレームを読み取るクラス。"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = setup_logger(level=config.log_level)
        self._capture: Optional[cv2.VideoCapture] = None

    @property
    def is_open(self) -> bool:
        """カメラが開いているか。"""
        return self._capture is not None and self._capture.isOpened()

    def _camera_busy_hint(self, index: int) -> str:
        """カメラ使用中の可能性がある場合のヒント。"""
        dev = Path(f"/dev/video{index}")
        if not dev.exists():
            return f" Device {dev} does not exist."

        try:
            result = subprocess.run(
                ["fuser", str(dev)],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().replace("\n", " ")
                return (
                    f" Camera is in use (PIDs: {pids})."
                    " Stop duplicate instance:"
                    " systemctl --user stop face-chrome-killer"
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return " Ensure no other app is using the webcam."

    def open(self) -> None:
        """カメラを開き、解像度とFPSを設定する。"""
        if self.is_open:
            return

        index = self._config.camera_index
        self._logger.info("Opening camera index %s", index)

        capture = cv2.VideoCapture(index)
        if not capture.isOpened():
            capture.release()
            raise CameraError(
                f"Cannot open camera index {index}.{self._camera_busy_hint(index)}"
            )

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self._config.camera_fps)

        self._capture = capture
        self._logger.info(
            "Camera initialized (%dx%d @ %d FPS)",
            self._config.camera_width,
            self._config.camera_height,
            self._config.camera_fps,
        )

    def read(self) -> Optional[np.ndarray]:
        """1フレーム読み取る。失敗時は None。"""
        if not self.is_open:
            raise CameraError("Camera is not open")

        assert self._capture is not None
        success, frame = self._capture.read()
        if not success or frame is None:
            self._logger.warning("Failed to read frame from camera")
            return None
        return frame

    def release(self) -> None:
        """カメラリソースを解放する。"""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            self._logger.info("Camera released")

    def read_with_retry(self) -> Optional[np.ndarray]:
        """フレーム読み取り失敗時にカメラを再オープンしてリトライする。"""
        try:
            if not self.is_open:
                self.open()
            frame = self.read()
            if frame is not None:
                return frame
        except CameraError as exc:
            self._logger.error("Camera error: %s", exc)

        self._logger.warning(
            "Retrying camera in %s seconds",
            self._config.camera_retry_delay_seconds,
        )
        self.release()
        time.sleep(self._config.camera_retry_delay_seconds)
        return None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
