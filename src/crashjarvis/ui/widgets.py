"""Reusable visual widgets for the CrashJarvis desktop interface."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from crashjarvis.ui import theme


@dataclass(frozen=True, slots=True)
class AssistantVisualState:
    label: str
    color: str
    activity: float


VISUAL_STATES: dict[str, AssistantVisualState] = {
    "sleeping": AssistantVisualState("SLEEPING", theme.MUTED, 0.18),
    "listening": AssistantVisualState("LISTENING", theme.CYAN, 0.55),
    "transcribing": AssistantVisualState("TRANSCRIBING", theme.PURPLE, 0.7),
    "thinking": AssistantVisualState("THINKING", theme.AMBER, 1.0),
    "acting": AssistantVisualState("ACTING", theme.GREEN, 0.85),
    "speaking": AssistantVisualState("SPEAKING", theme.CYAN, 0.75),
    "stopped": AssistantVisualState("STOPPED", theme.RED, 0.0),
}


class JarvisCoreWidget(QWidget):
    """Animated state indicator drawn directly with Qt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(340, 340)
        self._state = VISUAL_STATES["sleeping"]
        self._phase = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    @property
    def state_label(self) -> str:
        return self._state.label

    def set_state(self, state: str) -> None:
        normalized = state.strip().casefold()
        if normalized not in VISUAL_STATES:
            choices = ", ".join(VISUAL_STATES)
            raise ValueError(f"Unknown UI state {state!r}. Expected: {choices}.")
        self._state = VISUAL_STATES[normalized]
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.018 + self._state.activity * 0.025) % 1.0
        self.update()

    def paintEvent(self, event: object) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        base_radius = side * 0.28
        color = QColor(self._state.color)

        glow = QRadialGradient(center, base_radius * 1.7)
        glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 70))
        glow.setColorAt(0.55, QColor(color.red(), color.green(), color.blue(), 20))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, base_radius * 1.7, base_radius * 1.7)

        for index, radius_scale in enumerate((1.0, 1.23, 1.47)):
            radius = base_radius * radius_scale
            rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
            arc_color = QColor(color)
            arc_color.setAlpha(210 - index * 48)
            pen = QPen(arc_color, 3.0 - index * 0.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            start = int((self._phase * 360.0 * (1 if index % 2 == 0 else -1) + index * 83) * 16)
            span = int((78 + 46 * self._state.activity + index * 17) * 16)
            painter.drawArc(rect, start, span)
            painter.drawArc(rect, start + 180 * 16, int(span * 0.55))

        pulse = 1.0 + math.sin(self._phase * math.tau) * 0.035 * self._state.activity
        core_radius = base_radius * 0.65 * pulse
        gradient = QConicalGradient(center, self._phase * 360.0)
        gradient.setColorAt(0.0, color.lighter(145))
        gradient.setColorAt(0.5, color.darker(155))
        gradient.setColorAt(1.0, color.lighter(145))
        painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 230), 2))
        painter.setBrush(gradient)
        painter.drawEllipse(center, core_radius, core_radius)

        painter.setPen(QColor(theme.BACKGROUND))
        font = QFont("Segoe UI Variable", max(11, int(side * 0.035)))
        font.setBold(True)
        painter.setFont(font)
        text_rect = QRectF(
            center.x() - core_radius,
            center.y() - 15,
            core_radius * 2,
            30,
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "CJ")


class LatencyCard(QFrame):
    """A compact display for one measured pipeline duration."""

    def __init__(self, title: str, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("latencyCard")
        self.setMinimumHeight(76)

        accent_bar = QFrame()
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(f"background: {accent}; border-radius: 1px;")

        self._value = QLabel("—")
        value_font = QFont("Segoe UI Variable", 18)
        value_font.setBold(True)
        self._value.setFont(value_font)

        label = QLabel(title.upper())
        label.setObjectName("mutedLabel")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        text_layout.addWidget(label)
        text_layout.addWidget(self._value)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)
        layout.addWidget(accent_bar)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_milliseconds(self, value: float | None) -> None:
        self._value.setText("—" if value is None else f"{value:.0f} ms")


class StatusPill(QFrame):
    def __init__(self, text: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {theme.SURFACE_ALT}; border: 1px solid {theme.BORDER}; "
            "border-radius: 11px; }"
        )
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        label = QLabel(text)
        label.setStyleSheet("border: none; background: transparent; font-size: 11px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 3, 10, 3)
        layout.setSpacing(6)
        layout.addWidget(dot)
        layout.addWidget(label)