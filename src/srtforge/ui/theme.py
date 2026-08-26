"""Theme manager — dark (default) and light palettes.

The palette is exposed as a dataclass so widgets can read colors
programmatically (e.g. for the custom progress bar). QSS strings
provide the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtWidgets import QApplication

ThemeName = Literal["dark", "light", "system"]


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    bg_alt: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    success: str
    warning: str
    error: str
    log_info: str
    log_warn: str
    log_error: str


DARK = Palette(
    name="dark",
    bg="#0f1115",
    bg_alt="#15181f",
    surface="#1a1d24",
    surface_alt="#22262f",
    border="#2a2f3a",
    text="#e6e8ee",
    text_muted="#8a93a6",
    accent="#7c5cff",
    accent_hover="#9277ff",
    accent_text="#ffffff",
    success="#34d399",
    warning="#f59e0b",
    error="#ef4444",
    log_info="#9ca3af",
    log_warn="#fbbf24",
    log_error="#f87171",
)

LIGHT = Palette(
    name="light",
    bg="#f5f6f9",
    bg_alt="#ffffff",
    surface="#ffffff",
    surface_alt="#f0f2f7",
    border="#d8dce4",
    text="#1a1d24",
    text_muted="#5a6376",
    accent="#5b3df5",
    accent_hover="#7048ff",
    accent_text="#ffffff",
    success="#059669",
    warning="#d97706",
    error="#dc2626",
    log_info="#5a6376",
    log_warn="#b45309",
    log_error="#b91c1c",
)


def _palette(name: str) -> Palette:
    if name == "light":
        return LIGHT
    return DARK


def _qss(p: Palette) -> str:
    return f"""
    QMainWindow, QWidget {{
        background-color: {p.bg};
        color: {p.text};
    }}
    QFrame#card {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
    }}
    QPushButton {{
        background-color: {p.surface_alt};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {p.border};
    }}
    QPushButton#primary {{
        background-color: {p.accent};
        color: {p.accent_text};
        border: 1px solid {p.accent};
    }}
    QPushButton#primary:hover {{
        background-color: {p.accent_hover};
        border-color: {p.accent_hover};
    }}
    QPushButton:disabled {{
        color: {p.text_muted};
        background-color: {p.surface};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background-color: {p.surface_alt};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 4px 8px;
        selection-background-color: {p.accent};
        selection-color: {p.accent_text};
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        selection-background-color: {p.accent};
    }}
    QTableView, QTreeView, QListView {{
        background-color: {p.surface};
        alternate-background-color: {p.bg_alt};
        gridline-color: {p.border};
        border: 1px solid {p.border};
        border-radius: 6px;
    }}
    QHeaderView::section {{
        background-color: {p.surface_alt};
        color: {p.text_muted};
        padding: 6px;
        border: 0;
        border-bottom: 1px solid {p.border};
    }}
    QProgressBar {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 6px;
        text-align: center;
        color: {p.text};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: 5px;
    }}
    QStatusBar {{
        background-color: {p.surface};
        color: {p.text_muted};
        border-top: 1px solid {p.border};
    }}
    QMenuBar {{
        background-color: {p.surface};
        color: {p.text};
    }}
    QMenuBar::item:selected {{
        background-color: {p.accent};
        color: {p.accent_text};
    }}
    QMenu {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
    }}
    QMenu::item:selected {{
        background-color: {p.accent};
        color: {p.accent_text};
    }}
    QToolTip {{
        background-color: {p.surface_alt};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 4px;
    }}
    QSplitter::handle {{
        background-color: {p.border};
    }}
    QTabWidget::pane {{
        border: 1px solid {p.border};
        background-color: {p.surface};
    }}
    QTabBar::tab {{
        background-color: {p.surface_alt};
        color: {p.text_muted};
        padding: 6px 12px;
        border: 1px solid {p.border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        background-color: {p.surface};
        color: {p.text};
    }}
    """


def apply_theme(app: QApplication, name: str = "dark") -> Palette:
    """Apply the requested theme to the application and return the palette."""
    if name == "system":
        try:
            from PySide6.QtCore import QSettings
            from PySide6.QtGui import QStyleHints

            # Best-effort: follow the OS dark/light preference.
            if hasattr(QStyleHints, "colorScheme"):
                scheme = QStyleHints.colorScheme()
                if scheme == QStyleHints.ColorScheme.Light:
                    name = "light"
                else:
                    name = "dark"
            else:
                name = "dark"
        except Exception:  # noqa: BLE001
            name = "dark"
    p = _palette(name)
    app.setStyleSheet(_qss(p))
    return p
