import argparse
from dataclasses import dataclass
from time import sleep

import win32con
import win32gui
from pywinauto.keyboard import send_keys


ALLOWED_KEYS: dict[str, str] = {
    "enter": "{ENTER}",
    "tab": "{TAB}",
    "escape": "{ESC}",
}


class KeyDiagnosticError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WindowMatch:
    handle: int
    title: str


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely test sending one allow-listed key to exactly "
            "one visible Windows application window."
        )
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Case-insensitive text contained in the window title.",
    )
    parser.add_argument(
        "--key",
        required=True,
        choices=sorted(ALLOWED_KEYS),
        help="The single key to prepare or send.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually focus the selected window and send the key. "
            "Without this flag the diagnostic is read-only."
        ),
    )
    return parser.parse_args()


def find_visible_windows(title_query: str) -> list[WindowMatch]:
    normalized_query = title_query.strip().casefold()

    if not normalized_query:
        raise KeyDiagnosticError("The title query cannot be empty.")

    matches: list[WindowMatch] = []

    def collect_window(handle: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(handle):
            return True

        title = win32gui.GetWindowText(handle).strip()

        if title and normalized_query in title.casefold():
            matches.append(
                WindowMatch(
                    handle=handle,
                    title=title,
                )
            )

        return True

    win32gui.EnumWindows(collect_window, None)
    return matches


def focus_window(handle: int) -> None:
    if not win32gui.IsWindow(handle):
        raise KeyDiagnosticError(
            "The selected window no longer exists."
        )

    if win32gui.IsIconic(handle):
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)

    win32gui.SetForegroundWindow(handle)
    sleep(0.15)

    foreground_handle = win32gui.GetForegroundWindow()

    if foreground_handle != handle:
        foreground_title = win32gui.GetWindowText(
            foreground_handle
        ).strip()
        raise KeyDiagnosticError(
            "Windows did not give keyboard focus to the selected "
            f"window. Current foreground window: {foreground_title!r}."
        )


def main() -> None:
    arguments = parse_arguments()

    print("CrashJarvis single-key diagnostic")
    print(f"Mode: {'execute' if arguments.execute else 'read-only'}")
    print(f"Title query: {arguments.title!r}")
    print(f"Requested key: {arguments.key}")

    try:
        matches = find_visible_windows(arguments.title)

        print(f"Visible matches: {len(matches)}")

        for index, match in enumerate(matches, start=1):
            print(
                f"  {index}. handle={match.handle} | "
                f"title={match.title!r}"
            )

        if len(matches) != 1:
            raise KeyDiagnosticError(
                "Exactly one visible window must match. No key was sent."
            )

        target = matches[0]
        print(
            f"Selected: handle={target.handle} | "
            f"title={target.title!r}"
        )

        if not arguments.execute:
            print()
            print("[DRY RUN] The target is unambiguous. No key was sent.")
            print("Run the same command with --execute to continue.")
            return

        focus_window(target.handle)
        send_keys(
            ALLOWED_KEYS[arguments.key],
            pause=0.01,
            with_spaces=False,
        )

        print()
        print(
            f"[DISPATCHED] {arguments.key!r} was sent once to "
            f"{target.title!r}."
        )
        print(
            "The diagnostic verified the target and keyboard focus; "
            "verify the application-side result visually."
        )

    except KeyDiagnosticError as error:
        print()
        print(f"[BLOCKED] {error}")
        raise SystemExit(1) from error

    except Exception as error:
        print()
        print(f"[ERROR] Unexpected key diagnostic failure: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()