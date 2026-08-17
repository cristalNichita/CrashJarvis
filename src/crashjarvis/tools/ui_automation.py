from dataclasses import asdict
from typing import Any

from crashjarvis.desktop.ui_automation import (
    UiAutomationError,
    UiAutomationInspector,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class InspectWindowControlsTool(AgentTool):
    """Read-only inspection of controls in one exact window."""

    def __init__(
        self,
        inspector: UiAutomationInspector,
    ) -> None:
        self._inspector = inspector

    @property
    def name(self) -> str:
        return "inspect_window_controls"

    @property
    def description(self) -> str:
        return (
            "Inspect visible UI Automation controls inside one "
            "application window. This is a read-only tool. "
            "Call list_windows first and pass the exact window handle. "
            "Use query to search control names, types, automation IDs, "
            "or class names. Use control_types to restrict the result, "
            "for example Button, Edit, Text, ListItem, or Hyperlink. "
            "Prefer a specific query or control type instead of "
            "requesting every control."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact top-level window handle previously "
                        "returned by list_windows."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Optional case-insensitive search text matched "
                        "against the control metadata."
                    ),
                    "default": "",
                },
                "control_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional UI Automation control types to return."
                    ),
                    "default": [],
                },
                "visible_only": {
                    "type": "boolean",
                    "description": (
                        "Return only visible controls. This should "
                        "normally remain true."
                    ),
                    "default": True,
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of matching controls to return."
                    ),
                    "minimum": 1,
                    "maximum": 100,
                    "default": 40,
                },
            },
            "required": ["handle"],
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

        if handle <= 0:
            raise ToolExecutionError(
                "handle must be a positive integer."
            )

        query = arguments.get("query", "")

        if not isinstance(query, str):
            raise ToolExecutionError("query must be a string.")

        raw_control_types = arguments.get("control_types", [])

        if not isinstance(raw_control_types, list):
            raise ToolExecutionError(
                "control_types must be an array of strings."
            )

        if not all(
            isinstance(control_type, str)
            for control_type in raw_control_types
        ):
            raise ToolExecutionError(
                "Every control_types item must be a string."
            )

        visible_only = arguments.get("visible_only", True)

        if not isinstance(visible_only, bool):
            raise ToolExecutionError(
                "visible_only must be true or false."
            )

        limit = arguments.get("limit", 40)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ToolExecutionError("limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ToolExecutionError(
                "limit must be between 1 and 100."
            )

        normalized_control_types = [
            control_type.strip()
            for control_type in raw_control_types
            if control_type.strip()
        ]

        try:
            inspection = self._inspector.inspect_window(
                handle=handle,
                query=query.strip(),
                control_types=normalized_control_types,
                visible_only=visible_only,
                limit=limit,
            )

            return {
                "success": True,
                **asdict(inspection),
            }

        except UiAutomationError as error:
            raise ToolExecutionError(str(error)) from error


class ClickWindowControlTool(AgentTool):
    """Left-click a control from the latest inspection."""

    def __init__(
        self,
        inspector: UiAutomationInspector,
    ) -> None:
        self._inspector = inspector

    @property
    def name(self) -> str:
        return "click_window_control"

    @property
    def description(self) -> str:
        return (
            "Left-click one exact visible and enabled UI control. "
            "Call inspect_window_controls immediately before this tool, "
            "then pass the same window handle and an exact control_ref "
            "from that result. Never invent or reuse an old control_ref. "
            "This reports that the click was dispatched; it does not "
            "by itself prove the application's resulting state."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "The same window handle used for the immediately "
                        "preceding control inspection."
                    ),
                },
                "control_ref": {
                    "type": "string",
                    "description": (
                        "Exact control_ref from the immediately "
                        "preceding inspect_window_controls result."
                    ),
                    "pattern": "^[0-9a-f]{16}$",
                },
            },
            "required": ["handle", "control_ref"],
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

        if handle <= 0:
            raise ToolExecutionError(
                "handle must be a positive integer."
            )

        control_ref = arguments.get("control_ref")

        if not isinstance(control_ref, str):
            raise ToolExecutionError(
                "control_ref must be a string returned by "
                "inspect_window_controls."
            )

        try:
            result = self._inspector.click_control(
                handle=handle,
                control_ref=control_ref,
            )

            return result.to_dict()

        except UiAutomationError as error:
            raise ToolExecutionError(str(error)) from error