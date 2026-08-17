import argparse
import json

from crashjarvis.config import (
    SafetyConfig,
    WindowConfig,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
    WindowState,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.windows import SetWindowStateTool


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely test minimizing, maximizing, or restoring "
            "one application window."
        )
    )
    parser.add_argument(
        "--title",
        required=True,
        help=(
            "Case-insensitive part of the target window title. "
            "The match must be unambiguous."
        ),
    )
    parser.add_argument(
        "--state",
        required=True,
        choices=[
            WindowState.MINIMIZE.value,
            WindowState.MAXIMIZE.value,
            WindowState.RESTORE.value,
        ],
        help="Requested window state.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    window_config = WindowConfig()
    safety_config = SafetyConfig()

    manager = WindowManager(window_config)
    collection = manager.list_visible_windows()

    title_query = arguments.title.casefold()

    matches = [
        window
        for window in collection.windows
        if title_query in window.title.casefold()
    ]

    print("CrashJarvis window-state test")
    print(f"Title query: {arguments.title!r}")
    print(f"Requested state: {arguments.state}")
    print(f"Matches: {len(matches)}")
    print()

    if not matches:
        print("No matching visible window was found.")
        print("No action was performed.")
        return

    if len(matches) > 1:
        print("The title is ambiguous. Matching windows:")

        for window in matches:
            print(
                f"- handle={window.handle} | "
                f"title={window.title!r}"
            )

        print("No action was performed.")
        return

    target = matches[0]

    print(
        f"Selected: handle={target.handle} | "
        f"title={target.title!r}"
    )

    journal = OperationJournal(
        safety_config.operation_log_path
    )
    
    window_state_tool = SetWindowStateTool(
        window_manager=manager
    )

    registry = ToolRegistry(
        tools=[window_state_tool],
        journal=journal,
    )

    result = registry.execute(
        "set_window_state",
        {
            "handle": target.handle,
            "state": arguments.state,
        },
    )

    print()
    print(json.dumps(result, indent=2))
    print()
    print("[VERIFIED] Window state changed successfully.")


if __name__ == "__main__":
    main()