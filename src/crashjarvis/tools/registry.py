from time import perf_counter
from typing import Any, Iterable

from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class ToolRegistry:
    def __init__(
        self,
        tools: Iterable[AgentTool],
        journal: OperationJournal | None = None,
    ) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._journal = journal

        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(
                    f"Duplicate tool name: {tool.name}"
                )

            self._tools[tool.name] = tool

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return [
            tool.definition
            for tool in self._tools.values()
        ]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = perf_counter()
        tool = self._tools.get(name)

        if tool is None:
            error = ToolExecutionError(
                f"Unknown or unavailable tool: {name}"
            )

            self._record(
                tool_name=name,
                arguments=arguments,
                success=False,
                result={
                    "error": str(error),
                },
                started_at=started_at,
            )

            raise error

        try:
            result = tool.execute(arguments)

        except Exception as error:
            self._record(
                tool_name=name,
                arguments=arguments,
                success=False,
                result={
                    "error": str(error),
                },
                started_at=started_at,
            )

            raise

        self._record(
            tool_name=name,
            arguments=arguments,
            success=True,
            result=result,
            started_at=started_at,
        )

        return result

    def _record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        result: dict[str, Any],
        started_at: float,
    ) -> None:
        if self._journal is None:
            return

        duration_ms = (
            perf_counter() - started_at
        ) * 1000.0

        self._journal.record(
            tool_name=tool_name,
            arguments=arguments,
            success=success,
            result=result,
            duration_ms=duration_ms,
        )