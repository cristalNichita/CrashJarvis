import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class OperationJournal:
    def __init__(
        self,
        log_path: Path,
    ) -> None:
        self._log_path = log_path.resolve()
        self._lock = Lock()

    @property
    def log_path(self) -> Path:
        return self._log_path

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        result: dict[str, Any],
        duration_ms: float,
    ) -> None:
        entry = {
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "success": success,
            "result": result,
            "duration_ms": round(duration_ms, 3),
        }

        serialized_entry = json.dumps(
            entry,
            ensure_ascii=False,
        )

        with self._lock:
            self._log_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self._log_path.open(
                mode="a",
                encoding="utf-8",
            ) as file:
                file.write(serialized_entry)
                file.write("\n")