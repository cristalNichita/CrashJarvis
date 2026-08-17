from typing import Any

from crashjarvis.desktop.keyboard_controller import (
    KeyboardController,
    KeyPressError,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class PressKeyTool(AgentTool):
    """Press one explicitly requested allow-listed key."""

    def __init__(
        self,
        controller: KeyboardController,
    ) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "press_key"

    @property
    def description(self) -> str:
        return (
            "Press exactly one allow-listed keyboard key in one exact "
            "visible application window. The only supported keys are "
            "enter, tab, and escape. Use this only when the user's "
            "original request explicitly asks to press that key. Call "
            "list_windows first and pass its exact current handle. The "
            "tool focuses and verifies the target window before sending "
            "the key. It reports keyboard dispatch, not the resulting "
            "application state."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact visible window handle returned by "
                        "list_windows during the current request."
                    ),
                },
                "key": {
                    "type": "string",
                    "enum": ["enter", "tab", "escape"],
                    "description": (
                        "The single explicitly requested key to press."
                    ),
                },
            },
            "required": ["handle", "key"],
            "additionalProperties": False,
        }

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        handle = arguments.get("handle")

        if isinstance(handle, bool) or not isinstance(handle, int):
            raise ToolExecutionError(
                "handle must be an integer returned by list_windows."
            )

        key = arguments.get("key")

        if not isinstance(key, str):
            raise ToolExecutionError(
                "key must be one of: enter, tab, escape."
            )

        try:
            result = self._controller.press_key(
                handle=handle,
                key=key,
            )
            return result.to_dict()

        except KeyPressError as error:
            raise ToolExecutionError(str(error)) from error


class PressHotkeyTool(AgentTool):
    """Press one explicitly requested allow-listed hotkey."""

    def __init__(
        self,
        controller: KeyboardController,
    ) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "press_hotkey"

    @property
    def description(self) -> str:
        return (
            "Press exactly one allow-listed keyboard shortcut in one "
            "exact visible application window. The only supported "
            "shortcuts are ctrl+l and ctrl+a. Use this only when the "
            "user's original request explicitly asks for that exact "
            "shortcut. Call list_windows first and pass its exact "
            "current handle. The tool focuses and verifies the target "
            "window before sending the shortcut. It reports keyboard "
            "dispatch, not the resulting application state."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact visible window handle returned by "
                        "list_windows during the current request."
                    ),
                },
                "hotkey": {
                    "type": "string",
                    "enum": ["ctrl+l", "ctrl+a"],
                    "description": (
                        "The single explicitly requested shortcut."
                    ),
                },
            },
            "required": ["handle", "hotkey"],
            "additionalProperties": False,
        }

    @property
    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        handle = arguments.get("handle")

        if isinstance(handle, bool) or not isinstance(handle, int):
            raise ToolExecutionError(
                "handle must be an integer returned by list_windows."
            )

        hotkey = arguments.get("hotkey")

        if not isinstance(hotkey, str):
            raise ToolExecutionError(
                "hotkey must be one of: ctrl+l, ctrl+a."
            )

        try:
            result = self._controller.press_hotkey(
                handle=handle,
                hotkey=hotkey,
            )
            return result.to_dict()

        except KeyPressError as error:
            raise ToolExecutionError(str(error)) from error