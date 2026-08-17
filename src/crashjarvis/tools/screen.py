from typing import Any

from crashjarvis.intelligence.vision import (
    ScreenVisionAnalyzer,
    VisionAnalysisError,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class InspectScreenTool(AgentTool):
    def __init__(
        self,
        analyzer: ScreenVisionAnalyzer,
    ) -> None:
        self._analyzer = analyzer

    @property
    def name(self) -> str:
        return "inspect_screen"

    @property
    def description(self) -> str:
        return (
            "Capture and visually analyze the configured primary "
            "monitor using the local multimodal model. Use this "
            "only when information cannot be obtained through a "
            "faster structured tool such as list_windows or file "
            "tools. The screenshot is processed locally and "
            "deleted after analysis."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "One specific concise question about what "
                        "is currently visible on the screen."
                    ),
                },
            },
            "required": ["question"],
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
        question = arguments.get("question")

        if not isinstance(question, str):
            raise ToolExecutionError(
                "inspect_screen requires a string question."
            )

        try:
            result = self._analyzer.analyze(question)
        except VisionAnalysisError as error:
            raise ToolExecutionError(str(error)) from error

        return result.to_dict()