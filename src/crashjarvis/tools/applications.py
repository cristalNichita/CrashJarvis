from typing import Any
from time import perf_counter, sleep

from crashjarvis.config import ApplicationConfig
from crashjarvis.desktop.window_manager import WindowManager

from crashjarvis.desktop.application_catalog import (
    ApplicationCatalog,
    ApplicationCatalogError,
    ApplicationLaunchError,
)
from crashjarvis.tools.base import (
    AgentTool,
    ToolExecutionError,
)


class ApplicationAgentTool(AgentTool):
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


class SearchApplicationsTool(ApplicationAgentTool):
    def __init__(
        self,
        catalog: ApplicationCatalog,
    ) -> None:
        self._catalog = catalog

    @property
    def name(self) -> str:
        return "search_applications"

    @property
    def description(self) -> str:
        return (
            "Search the trusted local Windows application catalog. "
            "Returns application names and exact application IDs. "
            "Use this before launch_application. "
            "This tool does not launch or modify anything."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Application name or part of its name, "
                        "for example Chrome, Spotify, or vscode."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10,
                    "description": (
                        "Maximum number of matching applications."
                    ),
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        query = arguments.get("query")
        limit = arguments.get("limit", 10)

        if not isinstance(query, str):
            raise ToolExecutionError(
                "search_applications requires a string query."
            )

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
        ):
            raise ToolExecutionError(
                "search_applications limit must be an integer."
            )

        try:
            result = self._catalog.search(
                query=query,
                limit=limit,
            )
        except ApplicationCatalogError as error:
            raise ToolExecutionError(str(error)) from error

        return {
            "success": True,
            "query": query,
            "catalog_entries": (
                result.total_catalog_entries
            ),
            "match_count": len(result.applications),
            "truncated": result.truncated,
            "applications": [
                {
                    "application_id": (
                        application.application_id
                    ),
                    "name": application.name,
                    "source": application.source,
                }
                for application in result.applications
            ],
        }


class LaunchApplicationTool(ApplicationAgentTool):
    def __init__(
        self,
        catalog: ApplicationCatalog,
        window_manager: WindowManager,
        config: ApplicationConfig,
    ) -> None:
        self._catalog = catalog
        self._window_manager = window_manager
        self._config = config

    @property
    def name(self) -> str:
        return "launch_application"

    @property
    def description(self) -> str:
        return (
            "Launch one trusted application using an exact "
            "application ID previously returned by "
            "search_applications. It cannot execute arbitrary "
            "commands, accept command-line arguments, or launch "
            "an arbitrary file path. After requesting the launch, "
            "it attempts to verify that a matching visible window "
            "appeared."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": (
                        "Exact application ID returned by "
                        "search_applications."
                    ),
                },
            },
            "required": ["application_id"],
            "additionalProperties": False,
        }

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        application_id = arguments.get("application_id")

        if not isinstance(application_id, str):
            raise ToolExecutionError(
                "launch_application requires a string "
                "application_id."
            )

        application_id = application_id.strip()

        if not application_id:
            raise ToolExecutionError(
                "application_id cannot be empty."
            )

        try:
            application = self._catalog.get(application_id)
            launch_result = self._catalog.launch(
                application_id
            )
        except (
            ApplicationCatalogError,
            ApplicationLaunchError,
        ) as error:
            raise ToolExecutionError(str(error)) from error

        verification = self._wait_for_application_window(
            application.name
        )

        return {
            **launch_result,
            "window_verification": verification,
        }

    def _wait_for_application_window(
        self,
        application_name: str,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        deadline = (
            started_at
            + self._config.launch_verification_timeout_seconds
        )

        while True:
            try:
                collection = (
                    self._window_manager.list_visible_windows()
                )
            except Exception as error:
                return {
                    "verified": False,
                    "application_name": application_name,
                    "matching_windows": [],
                    "verification_ms": (
                        perf_counter() - started_at
                    ) * 1000.0,
                    "error": str(error),
                }

            matching_windows = [
                window
                for window in collection.windows
                if self._window_title_matches(
                    application_name=application_name,
                    window_title=window.title,
                )
            ]

            if matching_windows:
                return {
                    "verified": True,
                    "application_name": application_name,
                    "matching_windows": [
                        window.to_dict()
                        for window in matching_windows
                    ],
                    "verification_ms": (
                        perf_counter() - started_at
                    ) * 1000.0,
                }

            now = perf_counter()

            if now >= deadline:
                return {
                    "verified": False,
                    "application_name": application_name,
                    "matching_windows": [],
                    "verification_ms": (
                        now - started_at
                    ) * 1000.0,
                    "message": (
                        "Windows accepted the launch request, "
                        "but no matching visible window was found "
                        "before the verification timeout."
                    ),
                }

            remaining_seconds = deadline - now
            poll_seconds = (
                self._config
                .launch_verification_poll_interval_ms
                / 1000.0
            )

            sleep(
                min(
                    poll_seconds,
                    remaining_seconds,
                )
            )

    @staticmethod
    def _window_title_matches(
        application_name: str,
        window_title: str,
    ) -> bool:
        normalized_application = (
            application_name.strip().casefold()
        )
        normalized_title = window_title.strip().casefold()

        if not normalized_application or not normalized_title:
            return False

        if normalized_application in normalized_title:
            return True

        application_tokens = [
            token
            for token in normalized_application.split()
            if len(token) >= 3
        ]

        return bool(application_tokens) and all(
            token in normalized_title
            for token in application_tokens
        )