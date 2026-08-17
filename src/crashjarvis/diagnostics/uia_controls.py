import argparse
import json

from crashjarvis.config import (
    UiAutomationConfig,
    WindowConfig,
)
from crashjarvis.desktop.ui_automation import (
    UiAutomationError,
    UiAutomationInspector,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read filtered controls from one application window."
        )
    )
    parser.add_argument(
        "--title",
        required=True,
        help=(
            "Case-insensitive part of the target window title."
        ),
    )
    parser.add_argument(
        "--query",
        default="",
        help=(
            "Optional text matched against control names, types, "
            "automation IDs, and class names."
        ),
    )
    parser.add_argument(
        "--type",
        action="append",
        dest="control_types",
        default=None,
        help=(
            "Optional UIA control type. May be provided multiple "
            "times, for example --type Button --type Edit."
        ),
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include controls reported as hidden.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Maximum number of returned controls.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    window_config = WindowConfig()
    uia_config = UiAutomationConfig()

    window_manager = WindowManager(
        config=window_config
    )

    collection = window_manager.list_visible_windows()
    normalized_title = arguments.title.casefold()

    matches = [
        window
        for window in collection.windows
        if normalized_title in window.title.casefold()
    ]

    print("CrashJarvis filtered UI Automation test")
    print("Mode: read-only")
    print(f"Title query: {arguments.title!r}")
    print(f"Control query: {arguments.query!r}")
    print(f"Control types: {arguments.control_types}")
    print(
        f"Visible only: {not arguments.include_hidden}"
    )
    print(f"Limit: {arguments.limit}")
    print(f"Window matches: {len(matches)}")
    print()

    if not matches:
        print("No matching visible window was found.")
        return

    if len(matches) > 1:
        print("The target window is ambiguous:")

        for window in matches:
            print(
                f"- handle={window.handle} | "
                f"title={window.title!r}"
            )

        return

    target = matches[0]

    print(
        f"Selected: handle={target.handle} | "
        f"title={target.title!r}"
    )
    print("Initializing dedicated UIA worker...")

    try:
        inspector = UiAutomationInspector(
            config=uia_config
        )
    except UiAutomationError as error:
        print(f"[UIA ERROR] {error}")
        return

    try:
        inspection = inspector.inspect_window(
            handle=target.handle,
            query=arguments.query,
            control_types=arguments.control_types,
            visible_only=not arguments.include_hidden,
            limit=arguments.limit,
        )

        print()
        print(
            json.dumps(
                inspection.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
        )
        print()
        print(
            "[VERIFIED] Filtered UI controls were read "
            "successfully."
        )

    except UiAutomationError as error:
        print(f"[UIA ERROR] {error}")

    finally:
        inspector.close()


if __name__ == "__main__":
    main()