from typing import Any

from crashjarvis.desktop.window_manager import (
    WindowManager,
    WindowState,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class WindowAgentTool(AgentTool):
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


class ListWindowsTool(WindowAgentTool):
    def __init__(
        self,
        window_manager: WindowManager,
        backend_name: str,
    ) -> None:
        self._window_manager = window_manager
        self._backend_name = backend_name

    @property
    def name(self) -> str:
        return "list_windows"

    @property
    def description(self) -> str:
        return (
            "List visible top-level application windows. "
            "Returns each window's exact integer handle, title, "
            "process ID, minimized state, maximized state, and bounds. "
            "Use this before acting on a window. "
            "This tool does not modify any window."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ToolExecutionError(
                "list_windows does not accept arguments."
            )

        collection = self._window_manager.list_visible_windows()

        return {
            "success": True,
            "backend": self._backend_name,
            "window_count": len(collection.windows),
            "truncated": collection.truncated,
            "windows": [
                window.to_dict()
                for window in collection.windows
            ],
        }


class FocusWindowTool(WindowAgentTool):
    def __init__(self, window_manager: WindowManager) -> None:
        self._window_manager = window_manager

    @property
    def name(self) -> str:
        return "focus_window"

    @property
    def description(self) -> str:
        return (
            "Bring one visible application window to the foreground. "
            "The handle must be copied exactly from list_windows. "
            "Never invent or guess a handle."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact window handle returned by list_windows."
                    ),
                },
            },
            "required": ["handle"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        handle = arguments.get("handle")

        if isinstance(handle, bool) or not isinstance(handle, int):
            raise ToolExecutionError(
                "focus_window requires an integer handle."
            )

        try:
            return self._window_manager.focus_window(handle)
        except Exception as error:
            raise ToolExecutionError(str(error)) from error


class SetWindowStateTool(WindowAgentTool):
    def __init__(self, window_manager: WindowManager) -> None:
        self._window_manager = window_manager

    @property
    def name(self) -> str:
        return "set_window_state"

    @property
    def description(self) -> str:
        return (
            "Minimize, maximize, or restore one visible application "
            "window. The exact handle must first be obtained from "
            "list_windows. This tool cannot close applications."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact window handle returned by list_windows."
                    ),
                },
                "state": {
                    "type": "string",
                    "enum": [
                        WindowState.MINIMIZE.value,
                        WindowState.MAXIMIZE.value,
                        WindowState.RESTORE.value,
                    ],
                    "description": (
                        "Requested visible window state."
                    ),
                },
            },
            "required": ["handle", "state"],
            "additionalProperties": False,
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        handle = arguments.get("handle")
        raw_state = arguments.get("state")

        if isinstance(handle, bool) or not isinstance(handle, int):
            raise ToolExecutionError(
                "set_window_state requires an integer handle."
            )

        if not isinstance(raw_state, str):
            raise ToolExecutionError(
                "set_window_state requires a string state."
            )

        try:
            state = WindowState(raw_state)
        except ValueError as error:
            allowed_states = ", ".join(
                state.value for state in WindowState
            )
            raise ToolExecutionError(
                f"Unsupported window state {raw_state!r}. "
                f"Allowed states: {allowed_states}."
            ) from error

        try:
            return self._window_manager.set_window_state(
                handle,
                state,
            )
        except Exception as error:
            raise ToolExecutionError(str(error)) from error