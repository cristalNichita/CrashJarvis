from dataclasses import dataclass

from pywinauto import Desktop


@dataclass(frozen=True, slots=True)
class WindowInformation:
    handle: int
    process_id: int
    title: str

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def collect_visible_windows() -> tuple[
    list[WindowInformation],
    int,
]:
    desktop = Desktop(
        backend="uia",
        allow_magic_lookup=False,
    )

    collected: dict[int, WindowInformation] = {}
    failed_windows = 0

    for window in desktop.windows():
        try:
            if not window.is_visible():
                continue

            title = window.window_text().strip()

            if not title:
                continue

            handle = int(window.handle)
            process_id = int(
                window.element_info.process_id
            )
            rectangle = window.rectangle()

            collected[handle] = WindowInformation(
                handle=handle,
                process_id=process_id,
                title=title,
                left=rectangle.left,
                top=rectangle.top,
                right=rectangle.right,
                bottom=rectangle.bottom,
            )

        except Exception:
            failed_windows += 1

    windows = sorted(
        collected.values(),
        key=lambda window: window.title.casefold(),
    )

    return windows, failed_windows


def main() -> None:
    print("CrashJarvis Windows UI Automation test")
    print("Backend: UI Automation")
    print("Mode: read-only")
    print()
    print("Collecting visible top-level windows...")

    try:
        windows, failed_windows = (
            collect_visible_windows()
        )
    except Exception as error:
        print(f"[WINDOW ENUMERATION ERROR] {error}")
        return

    print()
    print(f"Visible titled windows: {len(windows)}")
    print()

    for index, window in enumerate(
        windows,
        start=1,
    ):
        print(
            f"{index:>2}. "
            f'PID={window.process_id:<6} | '
            f"HWND=0x{window.handle:08X} | "
            f"{window.width}x{window.height} | "
            f'"{window.title}"'
        )

    print()

    if failed_windows:
        print(
            f"Skipped inaccessible windows: "
            f"{failed_windows}"
        )

    print(
        "Windows UI Automation test "
        "completed successfully."
    )


if __name__ == "__main__":
    main()