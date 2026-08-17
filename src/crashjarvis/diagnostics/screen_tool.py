import argparse
import json

from crashjarvis.config import (
    LlmConfig,
    SafetyConfig,
    ScreenConfig,
    VisionConfig,
)
from crashjarvis.infrastructure.operation_journal import (
    OperationJournal,
)
from crashjarvis.intelligence.vision import (
    ScreenVisionAnalyzer,
)
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.screen import InspectScreenTool


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test local screen analysis through ToolRegistry."
        )
    )
    parser.add_argument(
        "--question",
        required=True,
        help=(
            "One concise question about the current screen."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    llm_config = LlmConfig()
    safety_config = SafetyConfig()
    screen_config = ScreenConfig()
    vision_config = VisionConfig()

    analyzer = ScreenVisionAnalyzer(
        llm_config=llm_config,
        screen_config=screen_config,
        vision_config=vision_config,
    )

    tool = InspectScreenTool(
        analyzer=analyzer
    )

    journal = OperationJournal(
        safety_config.operation_log_path
    )

    registry = ToolRegistry(
        tools=[tool],
        journal=journal,
    )

    print("CrashJarvis inspect_screen tool test")
    print(f"Question: {arguments.question!r}")
    print("Screenshot storage: temporary")
    print()

    result = registry.execute(
        "inspect_screen",
        {
            "question": arguments.question,
        },
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    print()

    if not result.get("success", False):
        raise RuntimeError(
            result.get(
                "error",
                "Screen inspection failed.",
            )
        )

    print(
        "[VERIFIED] inspect_screen completed through "
        "ToolRegistry."
    )


if __name__ == "__main__":
    main()