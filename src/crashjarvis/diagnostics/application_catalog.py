import argparse
import json
from time import perf_counter

from crashjarvis.desktop.application_catalog import (
    ApplicationCatalog,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the local Windows application catalog "
            "and search it without launching anything."
        )
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Application name or part of its name.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of displayed matches.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    print("CrashJarvis application catalog test")
    print("Mode: read-only")
    print(f"Search query: {arguments.query!r}")
    print()

    catalog = ApplicationCatalog()

    refresh_started_at = perf_counter()
    catalog_size = catalog.refresh()
    refresh_ms = (
        perf_counter() - refresh_started_at
    ) * 1000.0

    search_started_at = perf_counter()
    result = catalog.search(
        query=arguments.query,
        limit=arguments.limit,
    )
    search_ms = (
        perf_counter() - search_started_at
    ) * 1000.0

    print(f"Catalog entries: {catalog_size}")
    print(f"Catalog refresh: {refresh_ms:.1f} ms")
    print(f"Search: {search_ms:.3f} ms")
    print(f"Matches: {len(result.applications)}")
    print(f"Truncated: {result.truncated}")
    print()

    print(
        json.dumps(
            [
                application.to_dict()
                for application in result.applications
            ],
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print(
        "[VERIFIED] Application catalog search "
        "completed successfully."
    )


if __name__ == "__main__":
    main()