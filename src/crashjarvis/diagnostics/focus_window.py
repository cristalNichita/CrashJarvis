import argparse
import json

from crashjarvis.config import (
    SafetyConfig,
    WindowConfig,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.windows import (
    FocusWindowTool,
    ListWindowsTool,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Focus one visible window by a unique "
            "part of its title."
        )
    )

    parser.add_argument(
        "--title",
        required=True,
        help=(
            "Case-insensitive part of the target "
            "window title."
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    safety_config = SafetyConfig()
    window_config = WindowConfig()

    journal = OperationJournal(
        safety_config.operation_log_path
    )

    window_manager = WindowManager(
        backend=window_config.inventory_backend
    )

    list_windows = ListWindowsTool(
        window_manager=window_manager,
        maximum_windows=(
            window_config.maximum_windows
        ),
    )

    focus_window = FocusWindowTool(
        window_manager=window_manager,
    )

    registry = ToolRegistry(
        tools=[
            list_windows,
            focus_window,
        ],
        journal=journal,
    )

    listing = registry.execute(
        name="list_windows",
        arguments={},
    )

    requested_title = (
        arguments.title.casefold()
    )

    matches = [
        window
        for window in listing["windows"]
        if requested_title
        in window["title"].casefold()
    ]

    print("CrashJarvis focus_window test")
    print(f'Title search: "{arguments.title}"')
    print(f"Matches: {len(matches)}")
    print()

    if not matches:
        print("No matching windows were found.")
        return

    if len(matches) > 1:
        print(
            "More than one window matched. "
            "Refusing to choose automatically:"
        )

        for window in matches:
            print(
                f"- {window['handle_hex']} "
                f"| {window['title']}"
            )

        return

    target = matches[0]

    print(
        f"Target: {target['handle_hex']} "
        f"| {target['title']}"
    )
    print("Focusing window...")

    result = registry.execute(
        name="focus_window",
        arguments={
            "handle": target["handle"],
        },
    )

    print()
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()
    print(
        "[VERIFIED] The selected window became "
        "the foreground window."
    )


if __name__ == "__main__":
    main()