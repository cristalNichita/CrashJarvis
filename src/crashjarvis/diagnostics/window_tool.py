import json

from crashjarvis.config import (
    SafetyConfig,
    WindowConfig,
)
from crashjarvis.desktop.window_manager import (
    WindowManager,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.windows import ListWindowsTool


def main() -> None:
    safety_config = SafetyConfig()
    window_config = WindowConfig()

    journal = OperationJournal(
        safety_config.operation_log_path
    )

    window_manager = WindowManager(
        backend=window_config.inventory_backend
    )

    list_windows = ListWindowsTool(
        window_manager=window_manager,
        maximum_windows=(
            window_config.maximum_windows
        ),
    )

    registry = ToolRegistry(
        tools=[
            list_windows,
        ],
        journal=journal,
    )

    print("CrashJarvis list_windows tool test")
    print(
        f"Backend: "
        f"{window_config.inventory_backend}"
    )
    print("Mode: read-only")
    print()

    result = registry.execute(
        name="list_windows",
        arguments={},
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    if result["window_count"] < 1:
        raise RuntimeError(
            "Test failed: no visible windows were found."
        )

    print()
    print(
        f"[VERIFIED] Received "
        f"{result['window_count']} visible windows."
    )
    print(
        "list_windows tool test completed successfully."
    )


if __name__ == "__main__":
    main()