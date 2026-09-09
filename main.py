#!/usr/bin/env python3
"""Face Chrome Killer - メイン監視プロセス。"""

from __future__ import annotations

import argparse
import sys
import time

from src.camera import Camera, CameraError
from src.chrome_manager import ChromeManager
from src.config import get_config
from src.face_recognition_service import FaceRecognitionService
from src.logger import setup_logger
from src.state_machine import StateMachine


def parse_args() -> argparse.Namespace:
    """CLI引数を解析する。"""
    parser = argparse.ArgumentParser(description="Face Chrome Killer")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--test-camera",
        action="store_true",
        help="Test camera capture without face recognition",
    )
    parser.add_argument(
        "--test-chrome",
        action="store_true",
        help="Test Chrome process detection/termination",
    )
    parser.add_argument(
        "--force-chrome-kill",
        action="store_true",
        help="Actually terminate Chrome during --test-chrome (requires confirmation)",
    )
    return parser.parse_args()


def test_camera(config) -> int:
    """カメラテストモード。"""
    logger = setup_logger(level=config.log_level)
    logger.info("=== Camera Test Mode ===")

    camera = Camera(config)
    try:
        camera.open()
        for i in range(30):
            frame = camera.read()
            if frame is not None:
                logger.info("Frame %d captured: shape=%s", i + 1, frame.shape)
            else:
                logger.warning("Frame %d: read failed", i + 1)
            time.sleep(1.0 / config.camera_fps)
        logger.info("Camera test completed successfully")
        return 0
    except CameraError as exc:
        logger.error("Camera test failed: %s", exc)
        logger.info(
            "No camera available. Ensure /dev/video* exists and is accessible."
        )
        return 1
    finally:
        camera.release()


def test_chrome(config, force_kill: bool = False) -> int:
    """Chromeプロセス検出テスト。"""
    logger = setup_logger(level=config.log_level)
    logger.info("=== Chrome Process Test Mode ===")

    chrome = ChromeManager(config)
    running = chrome.is_running()
    logger.info("Chrome running: %s", running)

    if not running:
        logger.info("Chrome is not running. Detection test passed.")
        return 0

    if config.dry_run and not force_kill:
        logger.info("DRY_RUN=true: Would terminate Chrome but skipping")
        return 0

    if not force_kill:
        logger.warning(
            "Chrome is running. Use --force-chrome-kill to actually terminate."
        )
        logger.warning("Set DRY_RUN=false and --force-chrome-kill to test termination.")
        return 0

    logger.warning("*** WARNING: About to terminate Chrome! ***")
    success = chrome.terminate_gracefully()
    if success:
        logger.info("Chrome termination test passed")
        return 0

    logger.error("Chrome termination test failed")
    return 1


def run_monitor(config) -> int:
    """メイン監視ループ。"""
    logger = setup_logger(level=config.log_level)
    logger.info("Starting Face Chrome Killer")
    if config.dry_run:
        logger.info("DRY_RUN mode enabled - Chrome will NOT be terminated")

    face_service = FaceRecognitionService(config)
    try:
        face_service.load_registered_face()
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    camera = Camera(config)
    chrome = ChromeManager(config)
    state_machine = StateMachine(config)

    def on_trigger() -> None:
        """顔マッチ確認後のアクション。"""
        if not chrome.is_running():
            logger.info("Chrome is not running, skipping termination")
            return

        if config.dry_run:
            logger.info("Face match detected - Would terminate Chrome")
            return

        logger.info("Face match detected - Terminating Chrome")
        chrome.terminate_gracefully()

    state_machine.set_trigger_callback(on_trigger)

    last_recognition_time = 0.0

    try:
        while True:
            frame = camera.read_with_retry()
            if frame is None:
                continue

            now = time.monotonic()
            if now - last_recognition_time >= config.recognition_interval_seconds:
                last_recognition_time = now
                face_count, is_match, _ = face_service.analyze_frame(frame)

                if face_count > 0 and not is_match:
                    logger.debug("Face detected but no match")
                elif face_count > 0 and is_match:
                    logger.debug("Face match in progress")

                state_machine.update(face_count, is_match)

            time.sleep(1.0 / config.camera_fps)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        camera.release()

    return 0


def main() -> int:
    """エントリーポイント。"""
    args = parse_args()
    config = get_config()

    if args.debug:
        config.log_level = "DEBUG"

    if args.test_camera:
        return test_camera(config)
    if args.test_chrome:
        return test_chrome(config, force_kill=args.force_chrome_kill)

    return run_monitor(config)


if __name__ == "__main__":
    sys.exit(main())
