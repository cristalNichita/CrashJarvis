from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from mss import mss
from mss.tools import to_png

from crashjarvis.config import ScreenConfig


class ScreenCaptureError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MonitorInformation:
    index: int
    left: int
    top: int
    width: int
    height: int
    is_combined_desktop: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "is_combined_desktop": (
                self.is_combined_desktop
            ),
        }


@dataclass(frozen=True, slots=True)
class ScreenCaptureResult:
    monitor: MonitorInformation
    output_path: Path
    file_size_bytes: int
    capture_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "monitor": self.monitor.to_dict(),
            "output_path": str(self.output_path),
            "file_size_bytes": self.file_size_bytes,
            "capture_ms": self.capture_ms,
        }


class ScreenCaptureService:
    def __init__(self, config: ScreenConfig) -> None:
        self._config = config

    def list_monitors(self) -> list[MonitorInformation]:
        try:
            with mss() as capture:
                return [
                    self._create_monitor_information(
                        index=index,
                        raw_monitor=raw_monitor,
                    )
                    for index, raw_monitor
                    in enumerate(capture.monitors)
                ]
        except Exception as error:
            raise ScreenCaptureError(
                f"Could not enumerate monitors: {error}"
            ) from error

    def capture_monitor(
        self,
        monitor_index: int | None = None,
    ) -> ScreenCaptureResult:
        selected_index = (
            self._config.default_monitor_index
            if monitor_index is None
            else monitor_index
        )

        if (
            isinstance(selected_index, bool)
            or not isinstance(selected_index, int)
        ):
            raise ScreenCaptureError(
                "Monitor index must be an integer."
            )

        output_directory = (
            self._config.diagnostic_directory.resolve()
        )
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%S_%fZ")

        output_path = (
            output_directory
            / f"monitor_{selected_index}_{timestamp}.png"
        )

        started_at = perf_counter()

        try:
            with mss() as capture:
                monitors = capture.monitors

                if (
                    selected_index < 0
                    or selected_index >= len(monitors)
                ):
                    raise ScreenCaptureError(
                        f"Monitor index {selected_index} does "
                        f"not exist. Available indexes: "
                        f"0-{len(monitors) - 1}."
                    )

                raw_monitor = monitors[selected_index]
                screenshot = capture.grab(raw_monitor)

                to_png(
                    screenshot.rgb,
                    screenshot.size,
                    output=str(output_path),
                )

                monitor = self._create_monitor_information(
                    index=selected_index,
                    raw_monitor=raw_monitor,
                )

        except ScreenCaptureError:
            raise

        except Exception as error:
            raise ScreenCaptureError(
                f"Could not capture monitor "
                f"{selected_index}: {error}"
            ) from error

        capture_ms = (
            perf_counter() - started_at
        ) * 1000.0

        if not output_path.is_file():
            raise ScreenCaptureError(
                "The screenshot file was not created."
            )

        file_size_bytes = output_path.stat().st_size

        if file_size_bytes == 0:
            raise ScreenCaptureError(
                "The screenshot file is empty."
            )

        return ScreenCaptureResult(
            monitor=monitor,
            output_path=output_path,
            file_size_bytes=file_size_bytes,
            capture_ms=capture_ms,
        )

    @staticmethod
    def _create_monitor_information(
        index: int,
        raw_monitor: dict[str, int],
    ) -> MonitorInformation:
        return MonitorInformation(
            index=index,
            left=int(raw_monitor["left"]),
            top=int(raw_monitor["top"]),
            width=int(raw_monitor["width"]),
            height=int(raw_monitor["height"]),
            is_combined_desktop=index == 0,
        )