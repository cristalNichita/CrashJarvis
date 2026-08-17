import json

from crashjarvis.config import SafetyConfig
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.filesystem import (
    ListDirectoryTool,
    RenamePathTool,
)
from crashjarvis.tools.registry import ToolRegistry


def main() -> None:
    config = SafetyConfig()

    journal = OperationJournal(
        config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[
            RenamePathTool(
                allowed_root=config.test_directory,
            ),
            ListDirectoryTool(
                allowed_root=config.test_directory,
                maximum_entries=(
                    config.maximum_directory_entries
                ),
            ),
        ],
        journal=journal,
    )

    print("CrashJarvis safe rename test")
    print(f"Allowed root: {config.test_directory.resolve()}")
    print()

    rename_result = registry.execute(
        name="rename_path",
        arguments={
            "path": "Downloads/notes.txt",
            "new_name": "jarvis-notes.txt",
        },
    )

    print("Rename result:")
    print(
        json.dumps(
            rename_result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    listing_result = registry.execute(
        name="list_directory",
        arguments={
            "path": "Downloads",
        },
    )

    print("Downloads after rename:")
    print(
        json.dumps(
            listing_result,
            indent=2,
            ensure_ascii=False,
        )
    )

    old_name_exists = any(
        entry["name"] == "notes.txt"
        for entry in listing_result["entries"]
    )

    new_name_exists = any(
        entry["name"] == "jarvis-notes.txt"
        and entry["type"] == "file"
        for entry in listing_result["entries"]
    )

    if old_name_exists:
        raise RuntimeError(
            "Rename verification failed: "
            "notes.txt still exists."
        )

    if not new_name_exists:
        raise RuntimeError(
            "Rename verification failed: "
            "jarvis-notes.txt was not found."
        )

    print()
    print(
        "[VERIFIED] notes.txt was renamed "
        "to jarvis-notes.txt."
    )
    print(
        "Safe rename test completed successfully."
    )


if __name__ == "__main__":
    main()