import argparse
import json
from time import perf_counter

from crashjarvis.desktop.application_catalog import (
    ApplicationCatalog,
    ApplicationCatalogError,
    ApplicationLaunchError,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find and launch exactly one application from "
            "the trusted local application catalog."
        )
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Application name or part of its name.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    print("CrashJarvis safe application launch test")
    print(f"Query: {arguments.query!r}")
    print()

    catalog = ApplicationCatalog()

    try:
        refresh_started_at = perf_counter()
        catalog_size = catalog.refresh()
        refresh_ms = (
            perf_counter() - refresh_started_at
        ) * 1000.0

        result = catalog.search(
            query=arguments.query,
            limit=20,
        )
    except ApplicationCatalogError as error:
        print(f"[CATALOG ERROR] {error}")
        return

    print(f"Catalog entries: {catalog_size}")
    print(f"Catalog refresh: {refresh_ms:.1f} ms")
    print(f"Matches: {len(result.applications)}")
    print()

    if not result.applications:
        print("No matching application was found.")
        print("No application was launched.")
        return

    if len(result.applications) > 1:
        print("The application query is ambiguous:")

        for application in result.applications:
            print(
                f"- {application.name!r} | "
                f"source={application.source} | "
                f"id={application.application_id}"
            )

        print()
        print("Use a more specific query.")
        print("No application was launched.")
        return

    application = result.applications[0]

    print(
        f"Selected: {application.name!r} | "
        f"source={application.source} | "
        f"id={application.application_id}"
    )
    print(f"Trusted target: {application.launch_target}")
    print()

    launch_started_at = perf_counter()

    try:
        launch_result = catalog.launch(
            application.application_id
        )
    except ApplicationLaunchError as error:
        print(f"[LAUNCH ERROR] {error}")
        return

    launch_ms = (
        perf_counter() - launch_started_at
    ) * 1000.0

    print(
        json.dumps(
            launch_result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()
    print(f"Launch request: {launch_ms:.1f} ms")
    print(
        "[ACCEPTED] Windows accepted the application "
        "launch request."
    )


if __name__ == "__main__":
    main()