#!/usr/bin/env python3
"""Face Chrome Killer - 顔登録コマンド。"""

from __future__ import annotations

import sys
import time

import cv2

from src.camera import Camera, CameraError
from src.config import get_config
from src.face_recognition_service import FaceRecognitionService
from src.logger import setup_logger


INSTRUCTIONS = {
    "no_face": "Please look at the camera",
    "multiple": "Only one person should be visible",
    "too_small": "Move closer - keep your face inside the frame",
    "capturing": "Hold still... capturing sample {current}/{total}",
    "done": "Registration complete!",
    "inconsistent": "Samples inconsistent - please try again",
    "failed": "Registration failed - please try again",
}


def draw_overlay(frame, text: str, color=(0, 255, 0)) -> None:
    """フレームにテキストオーバーレイを描画する。"""
    cv2.putText(
        frame,
        text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
        cv2.LINE_AA,
    )


def register_face() -> int:
    """顔登録フローを実行する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    logger.info("=== Face Registration ===")

    camera = Camera(config)
    service = FaceRecognitionService(config)

    target_samples = config.registration_sample_count
    min_samples = config.registration_min_samples
    collected_encodings = []

    try:
        camera.open()
    except CameraError as exc:
        logger.error("Cannot open camera: %s", exc)
        return 1

    window_name = "Face Registration - Press Q to quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while len(collected_encodings) < target_samples:
            frame = camera.read()
            if frame is None:
                time.sleep(0.1)
                continue

            display = frame.copy()
            locations = service.detect_faces(frame)
            face_count = len(locations)

            if face_count == 0:
                draw_overlay(display, INSTRUCTIONS["no_face"], (0, 0, 255))
            elif face_count > 1:
                draw_overlay(display, INSTRUCTIONS["multiple"], (0, 0, 255))
            else:
                loc = locations[0]
                scale = 1.0 / FaceRecognitionService.RESIZE_FACTOR
                if not service.is_face_large_enough(loc, scale):
                    draw_overlay(display, INSTRUCTIONS["too_small"], (0, 165, 255))
                else:
                    encodings = service.encode_faces(frame, locations)
                    if encodings:
                        collected_encodings.append(encodings[0])
                        msg = INSTRUCTIONS["capturing"].format(
                            current=len(collected_encodings),
                            total=target_samples,
                        )
                        draw_overlay(display, msg, (0, 255, 0))
                        # 顔位置を描画
                        top, right, bottom, left = loc
                        s = FaceRecognitionService.RESIZE_FACTOR
                        cv2.rectangle(
                            display,
                            (int(left / s), int(top / s)),
                            (int(right / s), int(bottom / s)),
                            (0, 255, 0),
                            2,
                        )
                        time.sleep(0.3)

            progress = f"Samples: {len(collected_encodings)}/{target_samples}"
            cv2.putText(
                display, progress, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
            )

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("Registration cancelled by user")
                return 1

        if len(collected_encodings) < min_samples:
            logger.error(INSTRUCTIONS["failed"])
            return 1

        if not service.validate_sample_consistency(collected_encodings):
            logger.error(INSTRUCTIONS["inconsistent"])
            return 1

        avg_encoding = service.compute_average_encoding(collected_encodings)
        save_path = service.save_encoding(avg_encoding)
        logger.info(INSTRUCTIONS["done"])
        logger.info("Saved to: %s", save_path)
        return 0

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    sys.exit(register_face())
