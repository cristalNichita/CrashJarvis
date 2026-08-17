"""Colors and Qt stylesheet used by the CrashJarvis interface."""

BACKGROUND = "#050912"
SURFACE = "#0A1120"
SURFACE_ALT = "#0E192B"
BORDER = "#1B2B43"
TEXT = "#E8F5FF"
MUTED = "#7390A8"
CYAN = "#38D9FF"
CYAN_SOFT = "#153D53"
GREEN = "#45F0A8"
AMBER = "#FFB84D"
RED = "#FF5268"
PURPLE = "#A879FF"


APP_STYLESHEET = f"""
* {{
    font-family: "Segoe UI Variable", "Segoe UI";
    color: {TEXT};
}}

QMainWindow, QWidget#windowRoot {{
    background: {BACKGROUND};
}}

QFrame#titleBar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

QLabel#brand {{
    color: {TEXT};
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#versionLabel, QLabel#sectionHint, QLabel#mutedLabel {{
    color: {MUTED};
}}

QLabel#sectionTitle {{
    color: {TEXT};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#largeState {{
    color: {TEXT};
    font-size: 26px;
    font-weight: 700;
}}

QLabel#transcriptText {{
    color: {TEXT};
    font-size: 16px;
    line-height: 1.4;
}}

QLabel#jarvisText {{
    color: {CYAN};
    font-size: 16px;
    line-height: 1.4;
}}

QFrame#panel, QFrame#latencyCard, QFrame#transcriptPanel {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

QFrame#latencyCard:hover {{
    border-color: {CYAN_SOFT};
    background: {SURFACE_ALT};
}}

QPushButton {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    border-color: {CYAN};
    color: {CYAN};
}}

QPushButton:pressed {{
    background: {CYAN_SOFT};
}}

QPushButton#windowButton {{
    border: none;
    border-radius: 0;
    background: transparent;
    min-width: 42px;
    min-height: 38px;
    padding: 0;
}}

QPushButton#windowButton:hover {{
    background: {SURFACE_ALT};
    color: {TEXT};
}}

QPushButton#closeButton {{
    border: none;
    border-radius: 0;
    background: transparent;
    min-width: 46px;
    min-height: 38px;
    padding: 0;
}}

QPushButton#closeButton:hover {{
    background: {RED};
    color: white;
}}

QPushButton#emergencyButton {{
    color: {RED};
    border-color: #5B2632;
    background: #211018;
}}

QPushButton#emergencyButton:hover {{
    color: white;
    background: {RED};
    border-color: {RED};
}}

QPushButton#micButton[muted="true"] {{
    color: {RED};
    border-color: #5B2632;
}}

QTextEdit#eventLog {{
    background: transparent;
    border: none;
    color: {MUTED};
    selection-background-color: {CYAN_SOFT};
    font-family: "Cascadia Mono", Consolas;
    font-size: 11px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""
