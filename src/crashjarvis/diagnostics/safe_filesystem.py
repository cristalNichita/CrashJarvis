import json

from crashjarvis.config import SafetyConfig
from crashjarvis.tools.base import ToolExecutionError
from crashjarvis.tools.filesystem import (
    ListDirectoryTool,
)


def main() -> None:
    config = SafetyConfig()

    tool = ListDirectoryTool(
        allowed_root=config.test_directory,
        maximum_entries=(
            config.maximum_directory_entries
        ),
    )

    print("CrashJarvis safe filesystem test")
    print(f"Allowed directory: {config.test_directory.resolve()}")
    print()

    print("Test 1: reading sandbox/Downloads")

    result = tool.execute(
        {
            "path": "Downloads",
        }
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print("Test 2: attempting to escape the sandbox")

    try:
        tool.execute(
            {
                "path": "../",
            }
        )
    except ToolExecutionError as error:
        print(f"[BLOCKED AS EXPECTED] {error}")
    else:
        raise RuntimeError(
            "Security test failed: path traversal "
            "was not blocked."
        )

    print()
    print("Safe filesystem test completed successfully.")


if __name__ == "__main__":
    main()