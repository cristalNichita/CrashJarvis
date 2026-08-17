"""Standalone screenshot diagnostic without Whisper, Qwen, or Kokoro."""

from __future__ import annotations

import argparse

from crashjarvis.config import ScreenConfig
from crashjarvis.desktop.screenshot_service import (
    ScreenshotError,
    ScreenshotService,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one local Windows monitor as a PNG.",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=None,
        help=(
            "Physical monitor index. Index 0 captures the combined "
            "desktop. The configured default is used when omitted."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    config = ScreenConfig()
    monitor_index = (
        config.default_monitor_index
        if arguments.monitor is None
        else arguments.monitor
    )

    service = ScreenshotService(config.screenshot_directory)

    print("CrashJarvis screenshot diagnostic")
    print("Mode: local capture only")
    print("Network use: none")
    print(f"Monitor index: {monitor_index}")
    print(f"Output directory: {service.output_directory}")
    print()

    try:
        result = service.capture(monitor_index)
    except ScreenshotError as error:
        raise SystemExit(f"[FAILED] {error}") from error

    print(f"Screenshot: {result.path}")
    print(
        f"Resolution: {result.width}x{result.height} | "
        f"position: {result.left},{result.top}"
    )
    print(f"File size: {result.size_bytes} bytes")
    print(f"Capture: {result.capture_ms:.1f} ms")
    print()
    print("[VERIFIED] Screenshot saved successfully.")


if __name__ == "__main__":
    main()