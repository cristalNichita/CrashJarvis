"""Agent tool for saving local screenshots without visual analysis."""

from __future__ import annotations

from typing import Any

from crashjarvis.desktop.screenshot_service import (
    ScreenshotError,
    ScreenshotService,
)
from crashjarvis.tools.base import AgentTool, ToolExecutionError


class TakeScreenshotTool(AgentTool):
    """Save one monitor as a PNG when the user explicitly requests it."""

    def __init__(
        self,
        service: ScreenshotService,
        default_monitor_index: int,
    ) -> None:
        self._service = service
        self._default_monitor_index = default_monitor_index

    @property
    def name(self) -> str:
        return "take_screenshot"

    @property
    def description(self) -> str:
        return (
            "Take and save a PNG screenshot of a Windows monitor. "
            "Use this tool only when the user explicitly asks to take, "
            "capture, or save a screenshot. This tool does not analyze "
            "the image. Use inspect_screen instead when the task requires "
            "understanding what is visible on the screen. Monitor index 0 "
            "captures the combined desktop; physical monitors start at 1."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "monitor_index": {
                    "type": "integer",
                    "minimum": 0,
                    "description": (
                        "Monitor to capture. Omit this value to use the "
                        "configured default monitor. Index 0 captures all "
                        "monitors as one combined desktop."
                    ),
                },
            },
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

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        monitor_index = arguments.get(
            "monitor_index",
            self._default_monitor_index,
        )

        if isinstance(monitor_index, bool) or not isinstance(
            monitor_index,
            int,
        ):
            raise ToolExecutionError(
                "monitor_index must be an integer."
            )

        if monitor_index < 0:
            raise ToolExecutionError(
                "monitor_index cannot be negative."
            )

        try:
            result = self._service.capture(monitor_index)
        except ScreenshotError as error:
            raise ToolExecutionError(str(error)) from error

        return {
            "success": True,
            "path": str(result.path),
            "monitor_index": result.monitor_index,
            "left": result.left,
            "top": result.top,
            "width": result.width,
            "height": result.height,
            "size_bytes": result.size_bytes,
            "capture_ms": round(result.capture_ms, 3),
            "message": "Screenshot saved successfully.",
        }