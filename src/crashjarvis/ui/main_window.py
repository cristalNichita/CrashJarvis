"""Main PySide6 window for CrashJarvis."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crashjarvis.ui import theme
from crashjarvis.ui.widgets import JarvisCoreWidget, LatencyCard, StatusPill


class TitleBar(QFrame):
    def __init__(self, window: "CrashJarvisWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(48)

        brand = QLabel("CRASHJARVIS")
        brand.setObjectName("brand")
        version = QLabel("LOCAL AGENT  •  UI PREVIEW")
        version.setObjectName("versionLabel")

        minimize = self._window_button("—", window.showMinimized)
        maximize = self._window_button("□", window.toggle_maximized)
        close = self._window_button("×", window.close, close_button=True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(brand)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)

    @staticmethod
    def _window_button(text: str, callback: object, close_button: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("closeButton" if close_button else "windowButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class CrashJarvisWindow(QMainWindow):
    emergency_stop_requested = Signal()
    microphone_muted_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CrashJarvis")
        self.setMinimumSize(1120, 700)
        self.resize(1320, 820)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self._muted = False
        self._latency_cards: dict[str, LatencyCard] = {}
        self._current_user_text = ""
        self._current_jarvis_text = ""

        root = QWidget()
        root.setObjectName("windowRoot")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(TitleBar(self))
        root_layout.addWidget(self._build_content(), 1)

        self.setStyleSheet(theme.APP_STYLESHEET)
        self.set_state("sleeping")
        self.set_transcript("Say “Hey Jarvis” to begin.", "Ready for a local command.")
        self.append_event("UI shell initialized")

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QGridLayout(content)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(18)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 5)
        layout.setColumnStretch(2, 3)
        layout.setRowStretch(0, 5)
        layout.setRowStretch(1, 2)

        layout.addWidget(self._build_status_panel(), 0, 0)
        layout.addWidget(self._build_core_panel(), 0, 1)
        layout.addWidget(self._build_latency_panel(), 0, 2)
        layout.addWidget(self._build_transcript_panel(), 1, 0, 1, 2)
        layout.addWidget(self._build_event_panel(), 1, 2)
        return content

    @staticmethod
    def _panel() -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        return panel

    def _build_status_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        heading = QLabel("SYSTEM STATUS")
        heading.setObjectName("sectionTitle")
        self._state_label = QLabel("SLEEPING")
        self._state_label.setObjectName("largeState")
        self._state_detail = QLabel("Waiting for wake word")
        self._state_detail.setObjectName("sectionHint")
        self._state_detail.setWordWrap(True)

        badges = QVBoxLayout()
        badges.setSpacing(8)
        badges.addWidget(StatusPill("100% LOCAL", theme.GREEN))
        badges.addWidget(StatusPill("MICROPHONE ONLINE", theme.CYAN))
        badges.addWidget(StatusPill("QWEN READY", theme.PURPLE))
        badges.addWidget(StatusPill("WHISPER READY", theme.AMBER))

        self._mic_button = QPushButton("MUTE MICROPHONE")
        self._mic_button.setObjectName("micButton")
        self._mic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_button.clicked.connect(self._toggle_microphone)

        stop_button = QPushButton("EMERGENCY STOP")
        stop_button.setObjectName("emergencyButton")
        stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_button.clicked.connect(self._request_emergency_stop)

        layout.addWidget(heading)
        layout.addWidget(self._state_label)
        layout.addWidget(self._state_detail)
        layout.addSpacing(8)
        layout.addLayout(badges)
        layout.addStretch()
        layout.addWidget(self._mic_button)
        layout.addWidget(stop_button)
        return panel

    def _build_core_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(0)
        self._core = JarvisCoreWidget()
        self._core.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._core_caption = QLabel("VOICE AGENT CORE")
        self._core_caption.setObjectName("sectionTitle")
        self._core_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._core, 1)
        layout.addWidget(self._core_caption)
        return panel

    def _build_latency_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        heading = QLabel("LIVE LATENCY")
        heading.setObjectName("sectionTitle")
        hint = QLabel("Measured per pipeline stage")
        hint.setObjectName("sectionHint")
        layout.addWidget(heading)
        layout.addWidget(hint)

        definitions = (
            ("endpoint", "Speech endpoint", theme.CYAN),
            ("asr", "Recognition", theme.PURPLE),
            ("decision", "Decision", theme.AMBER),
            ("action", "Action", theme.GREEN),
            ("voice", "Voice start", theme.CYAN),
        )
        for key, title, color in definitions:
            card = LatencyCard(title, color)
            self._latency_cards[key] = card
            layout.addWidget(card)
        layout.addStretch()
        return panel

    def _build_transcript_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("transcriptPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        heading = QLabel("CONVERSATION")
        heading.setObjectName("sectionTitle")
        self._user_text = QLabel()
        self._user_text.setObjectName("transcriptText")
        self._user_text.setWordWrap(True)
        self._jarvis_text = QLabel()
        self._jarvis_text.setObjectName("jarvisText")
        self._jarvis_text.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(self._user_text)
        layout.addWidget(self._jarvis_text)
        layout.addStretch()
        return panel

    def _build_event_panel(self) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 12)
        heading = QLabel("OPERATION LOG")
        heading.setObjectName("sectionTitle")
        self._event_log = QTextEdit()
        self._event_log.setObjectName("eventLog")
        self._event_log.setReadOnly(True)
        layout.addWidget(heading)
        layout.addWidget(self._event_log, 1)
        return panel

    def toggle_maximized(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def set_state(self, state: str, detail: str | None = None) -> None:
        self._core.set_state(state)
        self._state_label.setText(self._core.state_label)
        details = {
            "sleeping": "Waiting for wake word",
            "listening": "Capturing your command",
            "transcribing": "Converting speech to text",
            "thinking": "Planning the next action",
            "acting": "Executing verified tools",
            "speaking": "Playing local voice response",
            "stopped": "Current task interrupted",
        }
        self._state_detail.setText(detail or details[state.casefold()])

    def set_latency(self, stage: str, milliseconds: float | None) -> None:
        if stage not in self._latency_cards:
            raise KeyError(f"Unknown latency stage: {stage}")
        self._latency_cards[stage].set_milliseconds(milliseconds)

    def set_transcript(self, user_text: str, jarvis_text: str) -> None:
        self._current_user_text = user_text
        self._current_jarvis_text = jarvis_text
        self._render_transcript()

    def set_partial_transcript(self, text: str) -> None:
        self._user_text.setText(f"HEARD  /  {text}")

    def set_user_transcript(self, text: str) -> None:
        self._current_user_text = text
        self._render_transcript()

    def set_jarvis_response(self, text: str) -> None:
        self._current_jarvis_text = text
        self._render_transcript()

    def show_runtime_error(self, message: str) -> None:
        self.set_state("stopped", "A runtime error occurred")
        self.append_event(f"ERROR  {message}")

    def runtime_finished(self) -> None:
        self.set_state("stopped", "CrashJarvis runtime is offline")
        self.append_event("Runtime stopped")

    def append_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._event_log.append(f"{timestamp}  {message}")

    def _render_transcript(self) -> None:
        self._user_text.setText(f"YOU  /  {self._current_user_text}")
        self._jarvis_text.setText(f"JARVIS  /  {self._current_jarvis_text}")

    def _request_emergency_stop(self) -> None:
        self.set_state("stopped", "Stop requested — finishing the current operation")
        self.append_event("Emergency stop requested")
        self.emergency_stop_requested.emit()

    def _toggle_microphone(self) -> None:
        self._muted = not self._muted
        self._mic_button.setProperty("muted", self._muted)
        self._mic_button.setText("UNMUTE MICROPHONE" if self._muted else "MUTE MICROPHONE")
        self._mic_button.style().unpolish(self._mic_button)
        self._mic_button.style().polish(self._mic_button)
        self.microphone_muted_changed.emit(self._muted)
