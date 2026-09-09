#!/usr/bin/env python3
"""Face Chrome Killer - 顔登録コマンド（kill / skip フロー分離）。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from src.camera import Camera, CameraError
from src.config import get_config
from src.face_recognition_service import FaceFlow, FaceRecognitionService
from src.logger import setup_logger


def parse_args() -> argparse.Namespace:
    """CLI引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="Register face users for kill or skip-minimize flow",
    )
    flow_group = parser.add_mutually_exclusive_group()
    flow_group.add_argument(
        "--kill",
        action="store_true",
        help="Register for kill flow (face match -> terminate Chrome)",
    )
    flow_group.add_argument(
        "--skip",
        action="store_true",
        help="Register for skip flow (face match -> skip minimize)",
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="User name (e.g. alice). Letters, numbers, _ and - only.",
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Register from image file instead of webcam",
    )
    parser.add_argument(
        "--list-kill",
        action="store_true",
        help="List kill-flow users",
    )
    parser.add_argument(
        "--list-skip",
        action="store_true",
        help="List skip-flow users",
    )
    parser.add_argument(
        "--delete-kill",
        type=str,
        metavar="NAME",
        help="Delete a kill-flow user",
    )
    parser.add_argument(
        "--delete-skip",
        type=str,
        metavar="NAME",
        help="Delete a skip-flow user",
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


def _service_for_flow(flow: FaceFlow) -> FaceRecognitionService:
    """フロー別 FaceRecognitionService を返す。"""
    return FaceRecognitionService(get_config(), flow=flow)


def list_users(flow: FaceFlow) -> int:
    """登録済みユーザー一覧を表示する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    service = _service_for_flow(flow)
    users = service.list_users()

    if not users:
        logger.info("No %s-flow users.", flow)
        logger.info("Register: python register.py --%s <name>", flow)
        return 0

    logger.info("%s-flow users (%d):", flow, len(users))
    for name in users:
        path = service._store.user_file_path(name)
        logger.info("  - %s (%s)", name, path)
    return 0


def delete_user(flow: FaceFlow, name: str) -> int:
    """ユーザーを削除する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    service = _service_for_flow(flow)

    if service.delete_user(name):
        logger.info("Deleted %s-flow user: %s", flow, name)
        return 0

    logger.error("%s-flow user not found: %s", flow, name)
    return 1


def register_from_image(image_path: str, user_name: str, flow: FaceFlow) -> int:
    """画像ファイルからユーザーを登録する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    logger.info("=== %s-flow registration from image: %s ===", flow, user_name)

    service = _service_for_flow(flow)
    try:
        save_path = service.register_from_image_file(Path(image_path), user_name)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Registration complete!")
    logger.info("Flow: %s", flow)
    logger.info("User: %s", user_name)
    logger.info("Saved to: %s", save_path)
    return 0


def register_face(user_name: str, flow: FaceFlow) -> int:
    """Webcam からユーザーを登録する。"""
    config = get_config()
    logger = setup_logger(level=config.log_level)
    logger.info("=== %s-flow registration (webcam): %s ===", flow, user_name)

    camera = Camera(config)
    service = _service_for_flow(flow)

    target_samples = config.registration_sample_count
    min_samples = config.registration_min_samples
    collected_encodings = []

    try:
        camera.open()
    except CameraError as exc:
        logger.error("Cannot open camera: %s", exc)
        return 1

    window_name = f"Register [{flow}]: {user_name} - Press Q to quit"
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
                factor = config.face_resize_factor
                scale = 1.0 / factor if factor > 0 else 1.0
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
                        s = factor if factor > 0 else 1.0
                        cv2.rectangle(
                            display,
                            (int(left / s), int(top / s)),
                            (int(right / s), int(bottom / s)),
                            (0, 255, 0),
                            2,
                        )
                        time.sleep(0.3)

            progress = (
                f"Flow: {flow} | User: {user_name} | "
                f"Samples: {len(collected_encodings)}/{target_samples}"
            )
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
        logger.info("Flow: %s", flow)
        logger.info("User: %s", user_name)
        logger.info("Saved to: %s", save_path)
        return 0

    finally:
        camera.release()
        cv2.destroyAllWindows()


def _resolve_flow(args: argparse.Namespace) -> FaceFlow | None:
    """CLI からフローを解決する。"""
    if args.kill:
        return "kill"
    if args.skip:
        return "skip"
    return None


def main() -> int:
    """エントリーポイント。"""
    args = parse_args()

    if args.list_kill:
        return list_users("kill")
    if args.list_skip:
        return list_users("skip")
    if args.delete_kill:
        return delete_user("kill", args.delete_kill)
    if args.delete_skip:
        return delete_user("skip", args.delete_skip)

    flow = _resolve_flow(args)
    if not args.name:
        print(
            "Usage:\n"
            "  python register.py --kill <name>              # kill flow (webcam)\n"
            "  python register.py --skip <name>              # skip flow (webcam)\n"
            "  python register.py --skip <name> --image photo.jpg\n"
            "  python register.py --list-kill\n"
            "  python register.py --list-skip\n"
            "  python register.py --delete-kill <name>\n"
            "  python register.py --delete-skip <name>",
            file=sys.stderr,
        )
        return 1

    if flow is None:
        print(
            "Error: specify --kill or --skip for registration.",
            file=sys.stderr,
        )
        return 1

    if args.image:
        return register_from_image(args.image, args.name, flow)
    return register_face(args.name, flow)


if __name__ == "__main__":
    sys.exit(main())
