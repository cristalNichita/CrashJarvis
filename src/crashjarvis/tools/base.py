from abc import ABC, abstractmethod
from typing import Any


class ToolExecutionError(RuntimeError):
    pass


class AgentTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def definition(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError