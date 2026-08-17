import argparse

from crashjarvis.desktop.keyboard_controller import (
    KeyboardController,
    KeyPressError,
)

import win32gui


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely test one allow-listed hotkey against exactly one "
            "visible Windows application window."
        )
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Case-insensitive text contained in the window title.",
    )
    parser.add_argument(
        "--hotkey",
        required=True,
        choices=["ctrl+l", "ctrl+a"],
        help="The single allow-listed hotkey to prepare or send.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually focus the selected window and send the hotkey. "
            "Without this flag the diagnostic is read-only."
        ),
    )
    return parser.parse_args()


def find_matching_windows(title_query: str) -> list[tuple[int, str]]:
    normalized_query = title_query.strip().casefold()

    if not normalized_query:
        raise KeyPressError("The title query cannot be empty.")

    matches: list[tuple[int, str]] = []

    def collect_window(handle: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(handle):
            return True

        title = win32gui.GetWindowText(handle).strip()

        if title and normalized_query in title.casefold():
            matches.append((handle, title))

        return True

    win32gui.EnumWindows(collect_window, None)
    return matches


def main() -> None:
    arguments = parse_arguments()
    controller = KeyboardController()

    print("CrashJarvis hotkey diagnostic")
    print(f"Mode: {'execute' if arguments.execute else 'read-only'}")
    print(f"Title query: {arguments.title!r}")
    print(f"Requested hotkey: {arguments.hotkey}")

    try:
        matches = find_matching_windows(arguments.title)
        print(f"Visible matches: {len(matches)}")

        for index, (handle, title) in enumerate(matches, start=1):
            print(
                f"  {index}. handle={handle} | title={title!r}"
            )

        if len(matches) != 1:
            raise KeyPressError(
                "Exactly one visible window must match. "
                "No hotkey was sent."
            )

        handle, title = matches[0]
        print(f"Selected: handle={handle} | title={title!r}")

        if not arguments.execute:
            print()
            print(
                "[DRY RUN] The target is unambiguous. "
                "No hotkey was sent."
            )
            print("Run the same command with --execute to continue.")
            return

        result = controller.press_hotkey(
            handle=handle,
            hotkey=arguments.hotkey,
        )

        print()
        print(f"[DISPATCHED] {result.message}")
        print(
            "The diagnostic verified the target and keyboard focus; "
            "verify the application-side result visually."
        )

    except KeyPressError as error:
        print()
        print(f"[BLOCKED] {error}")
        raise SystemExit(1) from error

    except Exception as error:
        print()
        print(f"[ERROR] Unexpected hotkey diagnostic failure: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()