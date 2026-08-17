"""Qt application entry point connected to the real CrashJarvis runtime."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

from crashjarvis.runtime import RuntimeControl
from crashjarvis.ui.main_window import CrashJarvisWindow


class RuntimeBridge(QObject):
    state_changed = Signal(str, str)
    partial_transcript_received = Signal(str)
    final_transcript_received = Signal(str)
    command_received_signal = Signal(str)
    response_ready_signal = Signal(str)
    latency_measured_signal = Signal(str, float)
    event_logged_signal = Signal(str)
    error_reported_signal = Signal(str)

    def state_changed_event(self, state: str, detail: str = "") -> None:
        self.state_changed.emit(state, detail)

    def partial_transcript(self, text: str) -> None:
        self.partial_transcript_received.emit(text)

    def final_transcript(self, text: str) -> None:
        self.final_transcript_received.emit(text)

    def command_received(self, text: str) -> None:
        self.command_received_signal.emit(text)

    def response_ready(self, text: str) -> None:
        self.response_ready_signal.emit(text)

    def latency_measured(self, stage: str, milliseconds: float) -> None:
        self.latency_measured_signal.emit(stage, milliseconds)

    def event_logged(self, message: str) -> None:
        self.event_logged_signal.emit(message)

    def error_reported(self, message: str) -> None:
        self.error_reported_signal.emit(message)


class RuntimeSinkAdapter:
    """Implements RuntimeEventSink without making the core import Qt."""

    def __init__(self, bridge: RuntimeBridge) -> None:
        self._bridge = bridge

    def state_changed(self, state: str, detail: str = "") -> None:
        self._bridge.state_changed_event(state, detail)

    def partial_transcript(self, text: str) -> None:
        self._bridge.partial_transcript(text)

    def final_transcript(self, text: str) -> None:
        self._bridge.final_transcript(text)

    def command_received(self, text: str) -> None:
        self._bridge.command_received(text)

    def response_ready(self, text: str) -> None:
        self._bridge.response_ready(text)

    def latency_measured(self, stage: str, milliseconds: float) -> None:
        self._bridge.latency_measured(stage, milliseconds)

    def event_logged(self, message: str) -> None:
        self._bridge.event_logged(message)

    def error_reported(self, message: str) -> None:
        self._bridge.error_reported(message)


class RuntimeThread(QThread):
    runtime_finished = Signal()

    def __init__(
        self,
        bridge: RuntimeBridge,
        control: RuntimeControl,
    ) -> None:
        super().__init__()
        self._sink = RuntimeSinkAdapter(bridge)
        self._control = control

    def run(self) -> None:
        try:
            # Import the automation stack only after QApplication exists.
            # This lets Qt configure Windows DPI awareness before pywinauto
            # and the Win32 automation modules are loaded.
            from crashjarvis.main import main as run_crashjarvis

            run_crashjarvis(
                event_sink=self._sink,
                runtime_control=self._control,
            )
        except Exception as error:
            self._sink.error_reported(f"Runtime stopped unexpectedly: {error}")
        finally:
            self.runtime_finished.emit()


def connect_runtime_to_window(
    bridge: RuntimeBridge,
    window: CrashJarvisWindow,
) -> None:
    bridge.state_changed.connect(window.set_state)
    bridge.partial_transcript_received.connect(window.set_partial_transcript)
    bridge.final_transcript_received.connect(window.set_user_transcript)
    bridge.command_received_signal.connect(window.set_user_transcript)
    bridge.response_ready_signal.connect(window.set_jarvis_response)
    bridge.latency_measured_signal.connect(window.set_latency)
    bridge.event_logged_signal.connect(window.append_event)
    bridge.error_reported_signal.connect(window.show_runtime_error)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("CrashJarvis")
    app.setOrganizationName("Crashbyt")

    window = CrashJarvisWindow()
    bridge = RuntimeBridge()
    control = RuntimeControl()
    worker = RuntimeThread(bridge, control)

    connect_runtime_to_window(bridge, window)

    window.emergency_stop_requested.connect(control.request_stop)
    window.microphone_muted_changed.connect(control.set_microphone_muted)
    app.aboutToQuit.connect(control.request_stop)

    worker.runtime_finished.connect(window.runtime_finished)

    window.set_state("sleeping", "Loading local AI models…")
    window.append_event("Starting CrashJarvis runtime")
    window.show()
    worker.start()

    exit_code = app.exec()

    control.request_stop()
    worker.wait()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()