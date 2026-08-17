import json

from crashjarvis.config import SafetyConfig
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.filesystem import (
    CreateDirectoryTool,
    ListDirectoryTool,
    MoveFileTool,
)
from crashjarvis.tools.registry import ToolRegistry


def print_result(
    title: str,
    result: dict[str, object],
) -> None:
    print(title)
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()


def main() -> None:
    config = SafetyConfig()

    journal = OperationJournal(
        config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[
            CreateDirectoryTool(
                allowed_root=config.test_directory,
            ),
            MoveFileTool(
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

    print("CrashJarvis safe file move test")
    print(f"Allowed root: {config.test_directory.resolve()}")
    print(f"Journal: {journal.log_path}")
    print()

    create_result = registry.execute(
        name="create_directory",
        arguments={
            "path": "Downloads/Recording",
        },
    )

    print_result(
        "Test 1: prepare destination directory",
        create_result,
    )

    move_result = registry.execute(
        name="move_file",
        arguments={
            "source_path": (
                "Downloads/first-video.mp4"
            ),
            "destination_directory": (
                "Downloads/Recording"
            ),
        },
    )

    print_result(
        "Test 2: move first-video.mp4",
        move_result,
    )

    downloads_result = registry.execute(
        name="list_directory",
        arguments={
            "path": "Downloads",
        },
    )

    recording_result = registry.execute(
        name="list_directory",
        arguments={
            "parent_directory": "Downloads",
            "directory_name": "Recording",
        },
    )

    print_result(
        "Test 3: Downloads after move",
        downloads_result,
    )

    print_result(
        "Test 4: Recording after move",
        recording_result,
    )

    source_still_present = any(
        entry["name"] == "first-video.mp4"
        for entry in downloads_result["entries"]
    )

    destination_present = any(
        entry["name"] == "first-video.mp4"
        and entry["type"] == "file"
        for entry in recording_result["entries"]
    )

    if source_still_present:
        raise RuntimeError(
            "Move verification failed: the source "
            "file is still present."
        )

    if not destination_present:
        raise RuntimeError(
            "Move verification failed: the destination "
            "file was not found."
        )

    print(
        "[VERIFIED] first-video.mp4 was removed "
        "from Downloads."
    )
    print(
        "[VERIFIED] first-video.mp4 exists inside "
        "Downloads/Recording."
    )
    print(
        "Safe file move test completed successfully."
    )


if __name__ == "__main__":
    main()