"""Fast local screenshot capture for Windows monitors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from mss import mss
from mss.tools import to_png


class ScreenshotError(RuntimeError):
    """Raised when a screenshot cannot be captured safely."""


@dataclass(frozen=True, slots=True)
class ScreenshotResult:
    path: Path
    monitor_index: int
    left: int
    top: int
    width: int
    height: int
    size_bytes: int
    capture_ms: float


class ScreenshotService:
    """Captures one monitor and stores the image as a local PNG."""

    def __init__(self, output_directory: Path) -> None:
        self._output_directory = output_directory.resolve()

    @property
    def output_directory(self) -> Path:
        return self._output_directory

    def capture(self, monitor_index: int) -> ScreenshotResult:
        if isinstance(monitor_index, bool) or not isinstance(
            monitor_index,
            int,
        ):
            raise ScreenshotError("monitor_index must be an integer.")

        if monitor_index < 0:
            raise ScreenshotError("monitor_index cannot be negative.")

        started_at = perf_counter()
        self._output_directory.mkdir(parents=True, exist_ok=True)

        try:
            with mss() as capture:
                monitors = capture.monitors

                if monitor_index >= len(monitors):
                    physical_monitor_count = max(0, len(monitors) - 1)
                    raise ScreenshotError(
                        f"Monitor index {monitor_index} does not exist. "
                        f"Available physical monitors: "
                        f"1 through {physical_monitor_count}; "
                        "index 0 captures the combined desktop."
                    )

                monitor = dict(monitors[monitor_index])
                screenshot = capture.grab(monitor)

                timestamp = datetime.now(timezone.utc).strftime(
                    "%Y%m%dT%H%M%S_%fZ"
                )
                filename = (
                    f"monitor_{monitor_index}_{timestamp}.png"
                )
                output_path = self._output_directory / filename
                temporary_path = output_path.with_suffix(".png.part")

                to_png(
                    screenshot.rgb,
                    screenshot.size,
                    output=str(temporary_path),
                )
                temporary_path.replace(output_path)

        except ScreenshotError:
            raise
        except Exception as error:
            raise ScreenshotError(
                f"Unable to capture monitor {monitor_index}: {error}"
            ) from error

        capture_ms = (perf_counter() - started_at) * 1000.0

        return ScreenshotResult(
            path=output_path,
            monitor_index=monitor_index,
            left=int(monitor["left"]),
            top=int(monitor["top"]),
            width=int(monitor["width"]),
            height=int(monitor["height"]),
            size_bytes=output_path.stat().st_size,
            capture_ms=capture_ms,
        )