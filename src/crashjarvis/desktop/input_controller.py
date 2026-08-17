import ctypes
from ctypes import wintypes
from threading import Lock
from time import sleep
import unicodedata

import win32gui

from crashjarvis.config import InputConfig
from crashjarvis.desktop.window_manager import (
    WindowManager,
)


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004

_ULONG_PTR = wintypes.WPARAM


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouse_data", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", _ULONG_PTR),
    ]


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("virtual_key", wintypes.WORD),
        ("scan_code", wintypes.WORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", _ULONG_PTR),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("message", wintypes.DWORD),
        ("parameter_low", wintypes.WORD),
        ("parameter_high", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("mouse", _MouseInput),
        ("keyboard", _KeyboardInput),
        ("hardware", _HardwareInput),
    ]


class _Input(ctypes.Structure):
    _anonymous_ = ("value",)

    _fields_ = [
        ("type", wintypes.DWORD),
        ("value", _InputUnion),
    ]


class TextInputError(RuntimeError):
    pass


class TextInputController:
    def __init__(
        self,
        config: InputConfig,
        window_manager: WindowManager,
    ) -> None:
        self._config = config
        self._window_manager = window_manager
        self._lock = Lock()

        self._send_input = ctypes.windll.user32.SendInput
        self._send_input.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(_Input),
            ctypes.c_int,
        )
        self._send_input.restype = wintypes.UINT

    def type_text(
        self,
        handle: int,
        text: str,
    ) -> dict[str, object]:
        self._validate(handle, text)

        with self._lock:
            focus_result = self._window_manager.focus_window(
                handle
            )

            sleep(
                self._config.focus_settle_ms / 1000.0
            )

            if win32gui.GetForegroundWindow() != handle:
                raise TextInputError(
                    "The target window did not remain in the "
                    "foreground. No text was entered."
                )

            utf16_units = self._to_utf16_units(text)

            chunk_size = (
                self._config.send_chunk_utf16_units
            )

            sent_events = 0

            for offset in range(
                0,
                len(utf16_units),
                chunk_size,
            ):
                chunk = utf16_units[
                    offset : offset + chunk_size
                ]

                sent_events += self._send_unicode_chunk(
                    chunk
                )

        expected_events = len(utf16_units) * 2

        if sent_events != expected_events:
            raise TextInputError(
                "Windows accepted only "
                f"{sent_events} of {expected_events} "
                "keyboard events."
            )

        return {
            "success": True,
            "target_handle": handle,
            "characters_requested": len(text),
            "utf16_units_sent": len(utf16_units),
            "keyboard_events_sent": sent_events,
            "focus_verified": True,
            "focus_result": focus_result,
        }

    def _validate(
        self,
        handle: int,
        text: str,
    ) -> None:
        if isinstance(handle, bool) or not isinstance(handle, int):
            raise TextInputError(
                "Target window handle must be an integer."
            )

        if not isinstance(text, str):
            raise TextInputError(
                "Text must be a string."
            )

        if not text:
            raise TextInputError(
                "Text cannot be empty."
            )

        if len(text) > self._config.maximum_text_characters:
            raise TextInputError(
                "Text exceeds the configured maximum of "
                f"{self._config.maximum_text_characters} "
                "characters."
            )

        unsupported_characters = [
            character
            for character in text
            if (
                character in {"\r", "\n", "\t"}
                or unicodedata.category(character) == "Cc"
            )
        ]

        if unsupported_characters:
            raise TextInputError(
                "Control characters, Enter, and Tab are not "
                "allowed in text input."
            )

    def _send_unicode_chunk(
        self,
        utf16_units: list[int],
    ) -> int:
        inputs: list[_Input] = []

        for unit in utf16_units:
            inputs.append(
                self._create_keyboard_input(
                    scan_code=unit,
                    flags=_KEYEVENTF_UNICODE,
                )
            )
            inputs.append(
                self._create_keyboard_input(
                    scan_code=unit,
                    flags=(
                        _KEYEVENTF_UNICODE
                        | _KEYEVENTF_KEYUP
                    ),
                )
            )

        input_array_type = _Input * len(inputs)
        input_array = input_array_type(*inputs)

        sent = self._send_input(
            len(inputs),
            input_array,
            ctypes.sizeof(_Input),
        )

        return int(sent)

    @staticmethod
    def _create_keyboard_input(
        scan_code: int,
        flags: int,
    ) -> _Input:
        return _Input(
            type=_INPUT_KEYBOARD,
            keyboard=_KeyboardInput(
                virtual_key=0,
                scan_code=scan_code,
                flags=flags,
                time=0,
                extra_info=0,
            ),
        )

    @staticmethod
    def _to_utf16_units(text: str) -> list[int]:
        encoded = text.encode("utf-16-le")

        return [
            int.from_bytes(
                encoded[index : index + 2],
                byteorder="little",
            )
            for index in range(0, len(encoded), 2)
        ]