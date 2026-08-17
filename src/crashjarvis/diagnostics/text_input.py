import argparse
import json

from crashjarvis.config import (
    InputConfig,
    WindowConfig,
)
from crashjarvis.desktop.input_controller import (
    TextInputController,
    TextInputError,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely type plain text into one unambiguous "
            "visible window."
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
        help=(
            "Plain text without Enter, Tab, or other "
            "control characters."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    window_config = WindowConfig()
    input_config = InputConfig()

    window_manager = WindowManager(
        config=window_config
    )
    controller = TextInputController(
        config=input_config,
        window_manager=window_manager,
    )

    collection = window_manager.list_visible_windows()
    normalized_query = arguments.title.casefold()

    matches = [
        window
        for window in collection.windows
        if normalized_query in window.title.casefold()
    ]

    print("CrashJarvis safe text-input test")
    print(f"Title query: {arguments.title!r}")
    print(f"Text length: {len(arguments.text)}")
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

    try:
        result = controller.type_text(
            handle=target.handle,
            text=arguments.text,
        )
    except TextInputError as error:
        print(f"[TEXT INPUT ERROR] {error}")
        return

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()
    print(
        "[SENT] Windows accepted all Unicode keyboard events."
    )
    print(
        "Visually confirm that the complete text appeared "
        "in the target window."
    )


if __name__ == "__main__":
    main()