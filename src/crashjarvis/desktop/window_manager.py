from dataclasses import dataclass
from enum import StrEnum

import win32con
import win32gui
import win32process
from pywinauto.controls.hwndwrapper import HwndWrapper

from crashjarvis.config import WindowConfig


class WindowEnumerationError(RuntimeError):
    pass


class WindowActionError(RuntimeError):
    pass


class WindowState(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class WindowInformation:
    handle: int
    process_id: int
    title: str
    class_name: str
    control_type: str
    minimized: bool
    maximized: bool
    bounds: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "handle": self.handle,
            "handle_hex": f"0x{self.handle:08X}",
            "process_id": self.process_id,
            "title": self.title,
            "class_name": self.class_name,
            "control_type": self.control_type,
            "minimized": self.minimized,
            "maximized": self.maximized,
            "bounds": self.bounds,
        }


@dataclass(frozen=True, slots=True)
class WindowCollection:
    windows: list[WindowInformation]
    truncated: bool


class WindowManager:
    def __init__(self, config: WindowConfig) -> None:
        self._config = config

    def list_visible_windows(self) -> WindowCollection:
        windows: list[WindowInformation] = []

        def collect_window(handle: int, _: object) -> bool:
            if not win32gui.IsWindowVisible(handle):
                return True

            title = win32gui.GetWindowText(handle).strip()

            if not title:
                return True

            try:
                information = self._read_window_information(handle)
            except Exception:
                return True

            windows.append(information)
            return True

        try:
            win32gui.EnumWindows(collect_window, None)
        except Exception as error:
            raise WindowEnumerationError(
                f"Could not enumerate Windows windows: {error}"
            ) from error

        windows.sort(
            key=lambda window: (
                window.title.casefold(),
                window.process_id,
                window.handle,
            )
        )

        truncated = len(windows) > self._config.maximum_windows

        return WindowCollection(
            windows=windows[: self._config.maximum_windows],
            truncated=truncated,
        )

    def focus_window(self, handle: int) -> dict[str, object]:
        self._validate_action_target(handle)

        before = self._read_window_information(handle)
        previous_foreground_handle = win32gui.GetForegroundWindow()

        try:
            wrapper = HwndWrapper(handle)

            if before.minimized:
                wrapper.restore()

            wrapper.set_focus()
        except Exception as error:
            raise WindowActionError(
                f"Could not focus window {handle}: {error}"
            ) from error

        foreground_handle = win32gui.GetForegroundWindow()

        if foreground_handle != handle:
            raise WindowActionError(
                "Windows did not confirm that the requested window "
                "became the foreground window."
            )

        after = self._read_window_information(handle)

        return {
            "success": True,
            "focused": True,
            "restored": before.minimized,
            "previous_foreground_handle": previous_foreground_handle,
            "foreground_handle": foreground_handle,
            "window": after.to_dict(),
        }

    def set_window_state(
        self,
        handle: int,
        state: WindowState,
    ) -> dict[str, object]:
        self._validate_action_target(handle)

        before = self._read_window_information(handle)

        show_command = {
            WindowState.MINIMIZE: win32con.SW_MINIMIZE,
            WindowState.MAXIMIZE: win32con.SW_MAXIMIZE,
            WindowState.RESTORE: win32con.SW_RESTORE,
        }[state]

        try:
            win32gui.ShowWindow(handle, show_command)
        except Exception as error:
            raise WindowActionError(
                f"Could not set window {handle} to "
                f"state {state.value!r}: {error}"
            ) from error

        after = self._read_window_information(handle)

        state_confirmed = {
            WindowState.MINIMIZE: after.minimized,
            WindowState.MAXIMIZE: after.maximized,
            WindowState.RESTORE: (
                not after.minimized
                and not after.maximized
            ),
        }[state]

        if not state_confirmed:
            raise WindowActionError(
                f"Windows did not confirm state {state.value!r} "
                f"for window {handle}."
            )

        return {
            "success": True,
            "requested_state": state.value,
            "state_verified": True,
            "before": before.to_dict(),
            "after": after.to_dict(),
        }

    def _validate_action_target(self, handle: int) -> None:
        if isinstance(handle, bool) or not isinstance(handle, int):
            raise WindowActionError(
                "Window handle must be an integer."
            )

        if not win32gui.IsWindow(handle):
            raise WindowActionError(
                f"Window handle does not exist: {handle}"
            )

        if not win32gui.IsWindowVisible(handle):
            raise WindowActionError(
                f"Window is not visible: {handle}"
            )

    def _read_window_information(
        self,
        handle: int,
    ) -> WindowInformation:
        title = win32gui.GetWindowText(handle).strip()
        _, process_id = win32process.GetWindowThreadProcessId(handle)

        left, top, right, bottom = win32gui.GetWindowRect(handle)

        return WindowInformation(
            handle=handle,
            process_id=process_id,
            title=title,
            class_name=win32gui.GetClassName(handle),
            control_type="Window",
            minimized=bool(win32gui.IsIconic(handle)),
            maximized=bool(
                win32gui.GetWindowPlacement(handle)[1]
                == win32con.SW_SHOWMAXIMIZED
            ),
            bounds={
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            },
        )