from dataclasses import dataclass
from time import sleep

import win32con
import win32gui
from pywinauto.keyboard import send_keys


class KeyPressError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class KeyPressResult:
    success: bool
    handle: int
    window_title: str
    key: str
    focus_verified: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "handle": self.handle,
            "window_title": self.window_title,
            "key": self.key,
            "focus_verified": self.focus_verified,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class HotkeyPressResult:
    success: bool
    handle: int
    window_title: str
    hotkey: str
    focus_verified: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "handle": self.handle,
            "window_title": self.window_title,
            "hotkey": self.hotkey,
            "focus_verified": self.focus_verified,
            "message": self.message,
        }


class KeyboardController:
    """Send one allow-listed key or hotkey to an exact window."""

    _KEY_SEQUENCES: dict[str, str] = {
        "enter": "{ENTER}",
        "tab": "{TAB}",
        "escape": "{ESC}",
    }
    _HOTKEY_SEQUENCES: dict[str, str] = {
        "ctrl+l": "^l",
        "ctrl+a": "^a",
    }

    def __init__(
        self,
        focus_settle_seconds: float = 0.15,
        key_pause_seconds: float = 0.01,
    ) -> None:
        if focus_settle_seconds < 0:
            raise ValueError(
                "focus_settle_seconds cannot be negative."
            )

        if key_pause_seconds < 0:
            raise ValueError(
                "key_pause_seconds cannot be negative."
            )

        self._focus_settle_seconds = focus_settle_seconds
        self._key_pause_seconds = key_pause_seconds

    @property
    def allowed_keys(self) -> tuple[str, ...]:
        return tuple(self._KEY_SEQUENCES)

    @property
    def allowed_hotkeys(self) -> tuple[str, ...]:
        return tuple(self._HOTKEY_SEQUENCES)

    def press_key(
        self,
        handle: int,
        key: str,
    ) -> KeyPressResult:
        normalized_key = key.strip().casefold()
        key_sequence = self._KEY_SEQUENCES.get(normalized_key)

        if key_sequence is None:
            allowed = ", ".join(self.allowed_keys)
            raise KeyPressError(
                f"Key {key!r} is not allowed. Allowed keys: {allowed}."
            )

        window_title = self._focus_window(handle)

        send_keys(
            key_sequence,
            pause=self._key_pause_seconds,
            with_spaces=False,
        )

        return KeyPressResult(
            success=True,
            handle=handle,
            window_title=window_title,
            key=normalized_key,
            focus_verified=True,
            message=(
                f"Key {normalized_key!r} was dispatched once to "
                f"{window_title!r}."
            ),
        )

    def press_hotkey(
        self,
        handle: int,
        hotkey: str,
    ) -> HotkeyPressResult:
        normalized_hotkey = (
            hotkey.strip().casefold().replace(" ", "")
        )
        hotkey_sequence = self._HOTKEY_SEQUENCES.get(
            normalized_hotkey
        )

        if hotkey_sequence is None:
            allowed = ", ".join(self.allowed_hotkeys)
            raise KeyPressError(
                f"Hotkey {hotkey!r} is not allowed. "
                f"Allowed hotkeys: {allowed}."
            )

        window_title = self._focus_window(handle)

        send_keys(
            hotkey_sequence,
            pause=self._key_pause_seconds,
            with_spaces=False,
        )

        return HotkeyPressResult(
            success=True,
            handle=handle,
            window_title=window_title,
            hotkey=normalized_hotkey,
            focus_verified=True,
            message=(
                f"Hotkey {normalized_hotkey!r} was dispatched once "
                f"to {window_title!r}."
            ),
        )

    def _focus_window(self, handle: int) -> str:
        if isinstance(handle, bool) or not isinstance(handle, int):
            raise KeyPressError("Window handle must be an integer.")

        if handle <= 0 or not win32gui.IsWindow(handle):
            raise KeyPressError(
                "The selected window does not exist anymore."
            )

        if not win32gui.IsWindowVisible(handle):
            raise KeyPressError(
                "The selected window is not currently visible."
            )

        window_title = win32gui.GetWindowText(handle).strip()

        if not window_title:
            raise KeyPressError(
                "The selected window does not have a visible title."
            )

        if win32gui.IsIconic(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)

        try:
            win32gui.SetForegroundWindow(handle)
        except Exception as error:
            raise KeyPressError(
                "Windows refused to focus the selected window."
            ) from error

        sleep(self._focus_settle_seconds)

        if win32gui.GetForegroundWindow() != handle:
            raise KeyPressError(
                "Keyboard focus could not be verified. "
                "No keyboard input was sent."
            )

        return window_title