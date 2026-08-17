import json

from crashjarvis.config import SafetyConfig
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.filesystem import (
    CreateDirectoryTool,
    ListDirectoryTool,
)
from crashjarvis.tools.registry import ToolRegistry


def print_json(value: object) -> None:
    print(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
    )


def main() -> None:
    config = SafetyConfig()

    journal = OperationJournal(
        config.operation_log_path
    )

    create_directory = CreateDirectoryTool(
        allowed_root=config.test_directory,
    )

    list_directory = ListDirectoryTool(
        allowed_root=config.test_directory,
        maximum_entries=(
            config.maximum_directory_entries
        ),
    )

    registry = ToolRegistry(
        tools=[
            create_directory,
            list_directory,
        ],
        journal=journal,
    )

    print("CrashJarvis safe directory creation test")
    print(f"Allowed root: {config.test_directory.resolve()}")
    print(f"Journal: {journal.log_path}")
    print()

    print("Test 1: creating Downloads/Recording")

    creation_result = registry.execute(
        name="create_directory",
        arguments={
            "parent_directory": "Downloads",
            "directory_name": "Recording",
        },
    )

    print_json(creation_result)
    print()

    print("Test 2: verifying Downloads contents")

    listing_result = registry.execute(
        name="list_directory",
        arguments={
            "path": "Downloads",
        },
    )

    print_json(listing_result)

    recording_found = any(
        entry["name"] == "Recording"
        and entry["type"] == "directory"
        for entry in listing_result["entries"]
    )

    if not recording_found:
        raise RuntimeError(
            "Directory verification failed: "
            "Recording was not found."
        )

    print()
    print("[VERIFIED] Downloads/Recording exists.")
    print(
        "Every operation was written to "
        f"{journal.log_path}"
    )
    print()
    print(
        "Safe directory creation test "
        "completed successfully."
    )


if __name__ == "__main__":
    main()