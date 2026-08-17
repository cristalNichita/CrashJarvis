import argparse
import json
from typing import Any

import win32gui

from crashjarvis.config import UiAutomationConfig
from crashjarvis.desktop.ui_automation import UiAutomationInspector
from crashjarvis.tools.ui_automation import (
    ClickWindowControlTool,
    InspectWindowControlsTool,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely inspect and click one exact UI Automation control."
        )
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Case-insensitive text contained in the window title.",
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Control search words, for example 'address bar'.",
    )
    parser.add_argument(
        "--type",
        dest="control_type",
        help="Optional UI Automation type, for example Edit.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually click the unique matching control.",
    )
    return parser.parse_args()


def find_visible_windows(title_query: str) -> list[dict[str, Any]]:
    normalized_query = title_query.strip().casefold()
    matches: list[dict[str, Any]] = []

    def collect(handle: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(handle):
            return True

        title = win32gui.GetWindowText(handle).strip()

        if title and normalized_query in title.casefold():
            matches.append(
                {
                    "handle": int(handle),
                    "title": title,
                }
            )

        return True

    win32gui.EnumWindows(collect, None)
    return matches


def main() -> None:
    arguments = parse_arguments()
    matches = find_visible_windows(arguments.title)

    print("CrashJarvis click-control test")
    print("Target window query:", repr(arguments.title))
    print("Control query:", repr(arguments.query))
    print("Execute click:", arguments.execute)
    print("Window matches:", len(matches))

    if len(matches) != 1:
        print()
        print(
            "[BLOCKED] Expected exactly one matching visible window."
        )

        for match in matches:
            print(
                f"- handle={match['handle']} | "
                f"title={match['title']!r}"
            )

        raise SystemExit(1)

    target = matches[0]
    print(
        f"Selected: handle={target['handle']} | "
        f"title={target['title']!r}"
    )

    inspector = UiAutomationInspector(
        config=UiAutomationConfig()
    )

    try:
        inspect_tool = InspectWindowControlsTool(
            inspector=inspector
        )
        click_tool = ClickWindowControlTool(
            inspector=inspector
        )

        control_types = (
            [arguments.control_type]
            if arguments.control_type
            else []
        )

        inspection = inspect_tool.execute(
            {
                "handle": target["handle"],
                "query": arguments.query,
                "control_types": control_types,
                "visible_only": True,
                "limit": 2,
            }
        )

        controls = inspection["controls"]

        print()
        print("[INSPECTION]")
        print(
            json.dumps(
                inspection,
                indent=2,
                ensure_ascii=False,
            )
        )

        if len(controls) != 1:
            print()
            print(
                "[BLOCKED] Expected exactly one matching control; "
                "nothing was clicked."
            )
            raise SystemExit(1)

        selected_control = controls[0]

        print()
        print(
            "Prepared target: "
            f"{selected_control['name']!r} | "
            f"type={selected_control['control_type']} | "
            f"control_ref={selected_control['control_ref']}"
        )

        if not arguments.execute:
            print(
                "[READ-ONLY] Add --execute to click this exact control."
            )
            return

        click_result = click_tool.execute(
            {
                "handle": target["handle"],
                "control_ref": selected_control["control_ref"],
            }
        )

        print()
        print("[CLICK RESULT]")
        print(
            json.dumps(
                click_result,
                indent=2,
                ensure_ascii=False,
            )
        )
        print()
        print(
            "[VERIFIED] The exact inspected control accepted a "
            "left-click."
        )

    finally:
        inspector.close()


if __name__ == "__main__":
    main()