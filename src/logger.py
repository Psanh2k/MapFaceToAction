"""ロギング設定。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "face_chrome_killer", level: str = "INFO") -> logging.Logger:
    """アプリケーションロガーを初期化して返す。"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソール出力
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)

    # ファイル出力
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "face_chrome_killer.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
