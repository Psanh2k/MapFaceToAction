"""アプリケーション設定の読み込みとデフォルト値管理。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトルートの .env を読み込む
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env_bool(key: str, default: bool) -> bool:
    """環境変数を bool に変換する。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    """環境変数を int に変換する。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return int(raw)


def _env_float(key: str, default: float) -> float:
    """環境変数を float に変換する。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return float(raw)


def _env_list(key: str, default: list[str]) -> list[str]:
    """カンマ区切りの環境変数をリストに変換する。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Config:
    """アプリケーション全体の設定。"""

    camera_index: int = field(default_factory=lambda: _env_int("CAMERA_INDEX", 0))
    camera_width: int = field(default_factory=lambda: _env_int("CAMERA_WIDTH", 640))
    camera_height: int = field(default_factory=lambda: _env_int("CAMERA_HEIGHT", 480))
    camera_fps: int = field(default_factory=lambda: _env_int("CAMERA_FPS", 10))
    camera_retry_delay_seconds: int = field(
        default_factory=lambda: _env_int("CAMERA_RETRY_DELAY_SECONDS", 5)
    )

    face_match_threshold: float = field(
        default_factory=lambda: _env_float("FACE_MATCH_THRESHOLD", 0.50)
    )
    face_resize_factor: float = field(
        default_factory=lambda: _env_float("FACE_RESIZE_FACTOR", 0.50)
    )
    face_detection_upsample: int = field(
        default_factory=lambda: _env_int("FACE_DETECTION_UPSAMPLE", 1)
    )
    face_detection_model: str = field(
        default_factory=lambda: os.getenv("FACE_DETECTION_MODEL", "hog").lower()
    )
    face_min_size: int = field(
        default_factory=lambda: _env_int("FACE_MIN_SIZE", 50)
    )
    face_encoding_jitters: int = field(
        default_factory=lambda: _env_int("FACE_ENCODING_JITTERS", 0)
    )
    required_match_seconds: float = field(
        default_factory=lambda: _env_float("REQUIRED_MATCH_SECONDS", 2.0)
    )
    require_single_face: bool = field(
        default_factory=lambda: _env_bool("REQUIRE_SINGLE_FACE", True)
    )
    recognition_interval_ms: int = field(
        default_factory=lambda: _env_int("RECOGNITION_INTERVAL_MS", 300)
    )
    match_reset_grace_ms: int = field(
        default_factory=lambda: _env_int("MATCH_RESET_GRACE_MS", 400)
    )

    chrome_process_names: list[str] = field(
        default_factory=lambda: _env_list(
            "CHROME_PROCESS_NAMES",
            ["google-chrome", "chrome", "chromium", "chromium-browser"],
        )
    )
    chrome_terminate_timeout: int = field(
        default_factory=lambda: _env_int("CHROME_TERMINATE_TIMEOUT", 5)
    )
    chrome_kill_scope: str = field(
        default_factory=lambda: os.getenv("CHROME_KILL_SCOPE", "main_only").lower()
    )

    trigger_cooldown_seconds: float = field(
        default_factory=lambda: _env_float("TRIGGER_COOLDOWN_SECONDS", 30.0)
    )
    require_face_absence_before_retrigger: bool = field(
        default_factory=lambda: _env_bool("REQUIRE_FACE_ABSENCE_BEFORE_RETRIGGER", True)
    )
    face_absence_seconds: float = field(
        default_factory=lambda: _env_float("FACE_ABSENCE_SECONDS", 3.0)
    )

    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))

    faces_data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("FACES_DATA_DIR", "data/faces"))
    )
    face_encoding_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("FACE_ENCODING_PATH", "data/face_encoding.pkl")
        )
    )
    registration_sample_count: int = field(
        default_factory=lambda: _env_int("REGISTRATION_SAMPLE_COUNT", 15)
    )
    registration_min_samples: int = field(
        default_factory=lambda: _env_int("REGISTRATION_MIN_SAMPLES", 10)
    )

    @property
    def project_root(self) -> Path:
        """プロジェクトルートディレクトリ。"""
        return _PROJECT_ROOT

    @property
    def faces_data_absolute_dir(self) -> Path:
        """マルチユーザー顔データディレクトリの絶対パス。"""
        path = self.faces_data_dir
        if path.is_absolute():
            return path
        return self.project_root / path

    @property
    def face_encoding_absolute_path(self) -> Path:
        """旧単一ファイル形式の絶対パス（移行用）。"""
        path = self.face_encoding_path
        if path.is_absolute():
            return path
        return self.project_root / path

    @property
    def recognition_interval_seconds(self) -> float:
        """認識間隔（秒）。"""
        return self.recognition_interval_ms / 1000.0

    @property
    def match_reset_grace_seconds(self) -> float:
        """マッチタイマーリセット猶予（秒）。"""
        return self.match_reset_grace_ms / 1000.0


def get_config() -> Config:
    """設定インスタンスを返す。"""
    return Config()
