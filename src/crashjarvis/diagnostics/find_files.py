import json

from crashjarvis.config import SafetyConfig
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.filesystem import FindFilesTool
from crashjarvis.tools.registry import ToolRegistry


def main() -> None:
    config = SafetyConfig()

    journal = OperationJournal(
        config.operation_log_path
    )

    find_files = FindFilesTool(
        allowed_root=config.test_directory,
        maximum_results=(
            config.maximum_search_results
        ),
        maximum_scanned_entries=(
            config.maximum_scanned_entries
        ),
    )

    registry = ToolRegistry(
        tools=[
            find_files,
        ],
        journal=journal,
    )

    print("CrashJarvis safe file search test")
    print(f"Allowed root: {config.test_directory.resolve()}")
    print()

    result = registry.execute(
        name="find_files",
        arguments={
            "directory": "Downloads",
            "extensions": [
                ".mp4",
                ".mov",
                ".mkv",
                ".avi",
                ".webm",
            ],
            "recursive": True,
            "sort_by": "modified_at",
            "sort_order": "descending",
            "limit": 10,
        },
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    files = result["files"]

    if not files:
        raise RuntimeError(
            "Test failed: no video files were found."
        )

    newest_file = files[0]

    print()
    print(
        f"[NEWEST VIDEO] "
        f"{newest_file['relative_path']}"
    )
    print(
        f"Modified: "
        f"{newest_file['modified_at_utc']}"
    )
    print(
        "Safe file search test completed successfully."
    )


if __name__ == "__main__":
    main()