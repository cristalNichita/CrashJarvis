"""Thread-safe controls and event reporting for the CrashJarvis runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from typing import Protocol


@dataclass(slots=True, weakref_slot=True)
class RuntimeControl:
    """Commands sent from the user interface to the agent loop."""

    stop_requested: Event = field(default_factory=Event)
    microphone_muted: Event = field(default_factory=Event)

    def request_stop(self) -> None:
        self.stop_requested.set()

    def set_microphone_muted(self, muted: bool) -> None:
        if muted:
            self.microphone_muted.set()
        else:
            self.microphone_muted.clear()


class RuntimeEventSink(Protocol):
    """Non-blocking notifications emitted by the agent runtime."""

    def state_changed(self, state: str, detail: str = "") -> None: ...

    def partial_transcript(self, text: str) -> None: ...

    def final_transcript(self, text: str) -> None: ...

    def command_received(self, text: str) -> None: ...

    def response_ready(self, text: str) -> None: ...

    def latency_measured(self, stage: str, milliseconds: float) -> None: ...

    def event_logged(self, message: str) -> None: ...

    def error_reported(self, message: str) -> None: ...


class NullRuntimeEventSink:
    """Default sink used by the existing console-only entry point."""

    def state_changed(self, state: str, detail: str = "") -> None:
        del state, detail

    def partial_transcript(self, text: str) -> None:
        del text

    def final_transcript(self, text: str) -> None:
        del text

    def command_received(self, text: str) -> None:
        del text

    def response_ready(self, text: str) -> None:
        del text

    def latency_measured(self, stage: str, milliseconds: float) -> None:
        del stage, milliseconds

    def event_logged(self, message: str) -> None:
        del message

    def error_reported(self, message: str) -> None:
        del message