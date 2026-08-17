import argparse
import json
from time import perf_counter

from crashjarvis.config import (
    ApplicationConfig,
    SafetyConfig,
    WindowConfig,
)
from crashjarvis.desktop.application_catalog import (
    ApplicationCatalog,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.applications import (
    LaunchApplicationTool,
    SearchApplicationsTool,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.desktop.window_manager import WindowManager


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test the safe application search and launch tools."
        )
    )
    parser.add_argument(
        "--query",
        required=True,
        help=(
            "Application name. The search must return "
            "exactly one result."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    print("CrashJarvis application tools test")
    print(f"Query: {arguments.query!r}")
    print()

    safety_config = SafetyConfig()
    application_config = ApplicationConfig()
    window_config = WindowConfig()
    window_manager = WindowManager(
        config=window_config
    )
    catalog = ApplicationCatalog()

    refresh_started_at = perf_counter()
    catalog_entries = catalog.refresh()
    refresh_ms = (
        perf_counter() - refresh_started_at
    ) * 1000.0

    print(f"Catalog entries: {catalog_entries}")
    print(f"Catalog refresh: {refresh_ms:.1f} ms")
    print()

    search_tool = SearchApplicationsTool(
        catalog=catalog
    )
    launch_tool = LaunchApplicationTool(
        catalog=catalog,
        window_manager=window_manager,
        config=application_config,
    )

    journal = OperationJournal(
        safety_config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[
            search_tool,
            launch_tool,
        ],
        journal=journal,
    )

    search_result = registry.execute(
        "search_applications",
        {
            "query": arguments.query,
            "limit": 10,
        },
    )

    print("[SEARCH RESULT]")
    print(
        json.dumps(
            search_result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    applications = search_result.get(
        "applications",
        [],
    )

    if len(applications) == 0:
        print("No matching application was found.")
        print("No application was launched.")
        return

    if len(applications) > 1:
        print(
            "The query is ambiguous. "
            "No application was launched."
        )
        return

    selected = applications[0]
    application_id = selected["application_id"]

    print(
        f"[SELECTED] {selected['name']!r} | "
        f"id={application_id}"
    )
    print()

    launch_result = registry.execute(
        "launch_application",
        {
            "application_id": application_id,
        },
    )

    print("[LAUNCH RESULT]")
    print(
        json.dumps(
            launch_result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    if not launch_result.get(
        "launch_request_accepted",
        False,
    ):
        raise RuntimeError(
            "Windows did not accept the launch request."
        )

    print(
        "[ACCEPTED] The trusted application launch "
        "request was accepted."
    )
    print(
        f"Journal: "
        f"{safety_config.operation_log_path.resolve()}"
    )


if __name__ == "__main__":
    main()