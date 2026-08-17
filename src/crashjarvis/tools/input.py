from typing import Any

from crashjarvis.desktop.input_controller import (
    TextInputController,
    TextInputError,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class TypeTextTool(AgentTool):
    def __init__(
        self,
        controller: TextInputController,
    ) -> None:
        self._controller = controller

    @property
    def name(self) -> str:
        return "type_text"

    @property
    def description(self) -> str:
        return (
            "Type plain Unicode text into one visible window. "
            "The exact integer window handle must first be obtained "
            "from list_windows. The tool cannot press Enter, Tab, "
            "keyboard shortcuts, or other control keys. Never use "
            "this tool for passwords, authentication codes, API "
            "keys, payment information, or other secrets."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "integer",
                    "description": (
                        "Exact target window handle returned by "
                        "list_windows."
                    ),
                },
                "text": {
                    "type": "string",
                    "description": (
                        "Plain visible text to enter. Enter, Tab, "
                        "and control characters are forbidden."
                    ),
                },
            },
            "required": [
                "handle",
                "text",
            ],
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
        text = arguments.get("text")

        if (
            isinstance(handle, bool)
            or not isinstance(handle, int)
        ):
            raise ToolExecutionError(
                "type_text requires an integer window handle."
            )

        if not isinstance(text, str):
            raise ToolExecutionError(
                "type_text requires a string text value."
            )

        try:
            return self._controller.type_text(
                handle=handle,
                text=text,
            )
        except TextInputError as error:
            raise ToolExecutionError(str(error)) from error