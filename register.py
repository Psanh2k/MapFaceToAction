#!/usr/bin/env python3
"""Face Chrome Killer - 顔登録コマンド（マルチユーザー対応）。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from src.camera import Camera, CameraError
from src.config import get_config
from src.face_recognition_service import FaceRecognitionService
from src.logger import setup_logger


def parse_args() -> argparse.Namespace:
    """CLI引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="Register face user for Face Chrome Killer",
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="User name (e.g. alice, bob). Letters, numbers, _ and - only.",
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Register from image file instead of webcam",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered users",
    )
    parser.add_argument(
        "--delete",
        type=str,
        metavar="NAME",
        help="Delete a registered user",
    )
    return parser.parse_args()


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


def list_users() -> int:
    """登録済みユーザー一覧を表示する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    service = FaceRecognitionService(config)
    users = service.list_users()

    if not users:
        logger.info("No registered users.")
        logger.info("Register: python register.py <name>")
        return 0

    logger.info("Registered users (%d):", len(users))
    for name in users:
        path = service._store.user_file_path(name)
        logger.info("  - %s (%s)", name, path)
    return 0


def delete_user(name: str) -> int:
    """ユーザーを削除する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    service = FaceRecognitionService(config)

    if service.delete_user(name):
        logger.info("Deleted user: %s", name)
        return 0

    logger.error("User not found: %s", name)
    return 1


def register_from_image(image_path: str, user_name: str) -> int:
    """画像ファイルからユーザーを登録する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    logger.info("=== Face Registration from Image: %s ===", user_name)

    service = FaceRecognitionService(config)
    try:
        save_path = service.register_from_image_file(Path(image_path), user_name)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Registration complete!")
    logger.info("User: %s", user_name)
    logger.info("Saved to: %s", save_path)
    return 0


def register_face(user_name: str) -> int:
    """Webcam からユーザーを登録する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    logger.info("=== Face Registration (webcam): %s ===", user_name)

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

    window_name = f"Register: {user_name} - Press Q to quit"
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

            progress = f"User: {user_name} | Samples: {len(collected_encodings)}/{target_samples}"
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
        save_path = service.register_user(user_name, avg_encoding, source="webcam")
        logger.info(INSTRUCTIONS["done"])
        logger.info("User: %s", user_name)
        logger.info("Saved to: %s", save_path)
        return 0

    finally:
        camera.release()
        cv2.destroyAllWindows()


def main() -> int:
    """エントリーポイント。"""
    args = parse_args()

    if args.list:
        return list_users()
    if args.delete:
        return delete_user(args.delete)

    if not args.name:
        print(
            "Usage:\n"
            "  python register.py <name>              # webcam\n"
            "  python register.py <name> --image photo.jpg\n"
            "  python register.py --list\n"
            "  python register.py --delete <name>",
            file=sys.stderr,
        )
        return 1

    if args.image:
        return register_from_image(args.image, args.name)
    return register_face(args.name)


if __name__ == "__main__":
    sys.exit(main())
