import argparse
import json

from crashjarvis.config import ScreenConfig
from crashjarvis.desktop.screen_capture import (
    ScreenCaptureError,
    ScreenCaptureService,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List local monitors and capture one screenshot."
        )
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=None,
        help=(
            "Monitor index. Uses the configured default "
            "when omitted."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    config = ScreenConfig()
    service = ScreenCaptureService(config)

    print("CrashJarvis screen-capture test")
    print("Mode: local read-only capture")
    print()

    try:
        monitors = service.list_monitors()
    except ScreenCaptureError as error:
        print(f"[SCREEN ERROR] {error}")
        return

    print("Available monitors:")

    for monitor in monitors:
        marker = (
            "combined desktop"
            if monitor.is_combined_desktop
            else "physical monitor"
        )

        print(
            f"- index={monitor.index} | "
            f"{monitor.width}x{monitor.height} | "
            f"position=({monitor.left}, {monitor.top}) | "
            f"{marker}"
        )

    print()

    try:
        result = service.capture_monitor(
            monitor_index=arguments.monitor
        )
    except ScreenCaptureError as error:
        print(f"[SCREEN ERROR] {error}")
        return

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
    )
    print()
    print("[VERIFIED] Screenshot file created successfully.")


if __name__ == "__main__":
    main()