"""Test the registered take_screenshot agent tool without AI models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from crashjarvis.config import SafetyConfig, ScreenConfig
from crashjarvis.desktop.screenshot_service import ScreenshotService
from crashjarvis.infrastructure.operation_journal import OperationJournal
from crashjarvis.tools.registry import ToolRegistry
from crashjarvis.tools.screenshot import TakeScreenshotTool


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute the take_screenshot tool locally.",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=None,
        help="Monitor index; omit to use the configured default.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    screen_config = ScreenConfig()
    safety_config = SafetyConfig()

    service = ScreenshotService(
        screen_config.screenshot_directory,
    )
    tool = TakeScreenshotTool(
        service=service,
        default_monitor_index=screen_config.default_monitor_index,
    )
    registry = ToolRegistry(
        tools=[tool],
        journal=OperationJournal(safety_config.operation_log_path),
    )

    tool_arguments: dict[str, int] = {}
    if arguments.monitor is not None:
        tool_arguments["monitor_index"] = arguments.monitor

    print("CrashJarvis take_screenshot tool test")
    print("Mode: local tool execution")
    print("Network use: none")
    print(f"Tool: {tool.name}")
    print(f"Arguments: {tool_arguments}")
    print()

    result = registry.execute(tool.name, tool_arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    screenshot_path = Path(str(result.get("path", "")))
    if not result.get("success") or not screenshot_path.is_file():
        raise SystemExit("[FAILED] Screenshot tool did not save a PNG.")

    print()
    print("[VERIFIED] take_screenshot completed successfully.")


if __name__ == "__main__":
    main()