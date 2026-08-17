import argparse
import json

from crashjarvis.config import (
    InputConfig,
    SafetyConfig,
    WindowConfig,
)
from crashjarvis.desktop.input_controller import (
    TextInputController,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.input import TypeTextTool
from crashjarvis.tools.registry import ToolRegistry


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test type_text through the real tool registry."
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
        "--text",
        required=True,
        help="Plain text to enter.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    input_config = InputConfig()
    safety_config = SafetyConfig()
    window_config = WindowConfig()

    window_manager = WindowManager(
        config=window_config
    )

    input_controller = TextInputController(
        config=input_config,
        window_manager=window_manager,
    )

    type_text_tool = TypeTextTool(
        controller=input_controller
    )

    operation_journal = OperationJournal(
        safety_config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[type_text_tool],
        journal=operation_journal,
    )

    collection = window_manager.list_visible_windows()
    normalized_query = arguments.title.casefold()

    matches = [
        window
        for window in collection.windows
        if normalized_query in window.title.casefold()
    ]

    print("CrashJarvis type_text tool test")
    print(f"Title query: {arguments.title!r}")
    print(f"Matches: {len(matches)}")
    print()

    if not matches:
        print("No matching visible window was found.")
        print("No text was entered.")
        return

    if len(matches) > 1:
        print("The target window is ambiguous:")

        for window in matches:
            print(
                f"- handle={window.handle} | "
                f"title={window.title!r}"
            )

        print()
        print("No text was entered.")
        return

    target = matches[0]

    print(
        f"Selected: handle={target.handle} | "
        f"title={target.title!r}"
    )
    print()

    result = registry.execute(
        "type_text",
        {
            "handle": target.handle,
            "text": arguments.text,
        },
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    if not result.get("success", False):
        raise RuntimeError(
            result.get(
                "error",
                "The type_text tool failed.",
            )
        )

    print(
        "[SENT] type_text completed through ToolRegistry."
    )
    print(
        f"Journal: "
        f"{operation_journal.log_path}"
    )


if __name__ == "__main__":
    main()