import argparse
import json
from typing import Any

from crashjarvis.config import (
    SafetyConfig,
    UiAutomationConfig,
    WindowConfig,
)
from crashjarvis.desktop.ui_automation import (
    UiAutomationInspector,
)
from crashjarvis.desktop.window_manager import WindowManager
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.ui_automation import (
    InspectWindowControlsTool,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test inspect_window_controls through the "
            "real CrashJarvis ToolRegistry."
        )
    )

    parser.add_argument(
        "--title",
        required=True,
        help=(
            "Case-insensitive part of the top-level "
            "window title."
        ),
    )

    parser.add_argument(
        "--query",
        default="",
        help=(
            "Optional text used to filter UI controls."
        ),
    )

    parser.add_argument(
        "--type",
        dest="control_types",
        action="append",
        default=[],
        help=(
            "Optional UI Automation control type. "
            "This argument may be repeated."
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
        default=20,
        help="Maximum number of controls to return.",
    )

    return parser.parse_args()


def find_matching_windows(
    window_manager: WindowManager,
    title_query: str,
) -> list[Any]:
    normalized_query = title_query.casefold()

    window_collection = (
        window_manager.list_visible_windows()
    )

    return [
        window
        for window in window_collection.windows
        if normalized_query in window.title.casefold()
    ]


def main() -> None:
    arguments = parse_arguments()

    safety_config = SafetyConfig()
    window_config = WindowConfig()
    ui_automation_config = UiAutomationConfig()

    print("CrashJarvis inspect-window-controls tool test")
    print("Mode: read-only")
    print(f"Title query: {arguments.title!r}")
    print(f"Control query: {arguments.query!r}")
    print(
        f"Control types: "
        f"{arguments.control_types or None}"
    )
    print(
        f"Visible only: "
        f"{not arguments.include_hidden}"
    )
    print(f"Limit: {arguments.limit}")
    print()

    window_manager = WindowManager(
        config=window_config,
    )

    matches = find_matching_windows(
        window_manager=window_manager,
        title_query=arguments.title,
    )

    print(f"Window matches: {len(matches)}")

    if not matches:
        print()
        print("No matching visible window was found.")
        return

    if len(matches) > 1:
        print()
        print(
            "Multiple windows matched. "
            "No window was selected:"
        )

        for window in matches:
            print(
                f"- handle={window.handle} | "
                f"title={window.title!r}"
            )

        print()
        print(
            "Use a more specific --title value so exactly "
            "one window matches."
        )
        return

    selected_window = matches[0]

    print(
        f"Selected: handle={selected_window.handle} | "
        f"title={selected_window.title!r}"
    )
    print("Initializing dedicated UIA worker...")
    print()

    inspector = UiAutomationInspector(
        config=ui_automation_config,
    )

    journal = OperationJournal(
        safety_config.operation_log_path,
    )

    tool = InspectWindowControlsTool(
        inspector=inspector,
    )

    registry = ToolRegistry(
        tools=[tool],
        journal=journal,
    )

    try:
        result = registry.execute(
            "inspect_window_controls",
            {
                "handle": selected_window.handle,
                "query": arguments.query,
                "control_types": (
                    arguments.control_types
                ),
                "visible_only": (
                    not arguments.include_hidden
                ),
                "limit": arguments.limit,
            },
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        if not result.get("success", False):
            print()
            print(
                "[FAILED] The tool returned an error."
            )
            return

        print()
        print(
            "[VERIFIED] inspect_window_controls "
            "completed through ToolRegistry."
        )

    finally:
        inspector.close()


if __name__ == "__main__":
    main()