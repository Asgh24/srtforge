"""LogView — color-coded QPlainTextEdit with auto-scroll toggle."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LEVEL_COLORS = {
    "INFO": "#9ca3af",
    "DEBUG": "#6b7280",
    "WARN": "#fbbf24",
    "WARNING": "#fbbf24",
    "ERROR": "#f87171",
    "SUCCESS": "#34d399",
}


class LogView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = QPlainTextEdit(self)
        self._edit.setReadOnly(True)
        self._edit.setMaximumBlockCount(5000)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        self._edit.setFont(font)
        layout.addWidget(self._edit, 1)

        controls = QHBoxLayout()
        self._auto = QCheckBox("Auto-scroll", self)
        self._auto.setChecked(True)
        controls.addWidget(self._auto)
        controls.addStretch(1)
        clear = QPushButton("Clear", self)
        clear.clicked.connect(self._edit.clear)
        controls.addWidget(clear)
        save = QPushButton("Save…", self)
        save.clicked.connect(self._save_to_file)
        controls.addWidget(save)
        layout.addLayout(controls)

    def append_log(self, level: str, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"{ts} [{level}] {text}"
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LEVEL_COLORS.get(level.upper(), "#9ca3af")))
        cursor.insertText(line + "\n", fmt)
        if self._auto.isChecked():
            sb = self._edit.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _save_to_file(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", "srtforge.log", "Log files (*.log);;All files (*)"
        )
        if path:
            Path(path).write_text(self._edit.toPlainText(), encoding="utf-8")
