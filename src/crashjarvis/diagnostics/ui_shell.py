"""Standalone visual test for the CrashJarvis PySide6 interface."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from crashjarvis.ui.main_window import CrashJarvisWindow


class UiDiagnostic:
    """Cycles real UI components through representative agent states."""

    def __init__(self, window: CrashJarvisWindow) -> None:
        self._window = window
        self._index = 0
        self._states = (
            ("sleeping", "Say “Hey Jarvis” to begin."),
            ("listening", "Find the newest video in Downloads."),
            ("transcribing", "Speech received. Building final transcript."),
            ("thinking", "Planning a safe multi-step task."),
            ("acting", "Checking the sandbox Downloads folder."),
            ("speaking", "The newest video is ready."),
        )
        self._timer = QTimer(window)
        self._timer.setInterval(2400)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

        window.emergency_stop_requested.connect(self._stop)
        window.microphone_muted_changed.connect(self._microphone_changed)
        self._advance()

    def _advance(self) -> None:
        state, text = self._states[self._index]
        self._window.set_state(state)
        self._window.set_transcript(text, self._response_for(state))
        self._window.append_event(f"Diagnostic state → {state.upper()}")

        samples = {
            "endpoint": 322.0,
            "asr": 234.0 + self._index * 9,
            "decision": 756.0 + self._index * 83,
            "action": 3.0 + self._index * 2,
            "voice": 417.0 + self._index * 14,
        }
        for stage, milliseconds in samples.items():
            self._window.set_latency(stage, milliseconds)

        self._index = (self._index + 1) % len(self._states)

    @staticmethod
    def _response_for(state: str) -> str:
        return {
            "sleeping": "Local models are loaded and standing by.",
            "listening": "Listening…",
            "transcribing": "Final transcription is being prepared.",
            "thinking": "I am deciding which tools are required.",
            "acting": "Running the selected safe tool.",
            "speaking": "Task complete. The result was verified.",
        }[state]

    def _stop(self) -> None:
        self._timer.stop()
        self._window.set_state("stopped")
        self._window.append_event("Emergency stop requested")

    def _microphone_changed(self, muted: bool) -> None:
        state = "muted" if muted else "online"
        self._window.append_event(f"Microphone → {state}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("CrashJarvis")
    app.setOrganizationName("Crashbyt")

    window = CrashJarvisWindow()
    UiDiagnostic(window)
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
