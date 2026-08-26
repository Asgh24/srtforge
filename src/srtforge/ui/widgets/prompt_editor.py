"""Prompt editor — a tabbed view of the default template + a custom override."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from srtforge.translate.prompt import CUSTOM_VARIABLES, DEFAULT_PROMPT


class PromptEditorDialog(QDialog):
    saved = Signal(str | None)  # None = use default

    def __init__(self, current_custom: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Translation prompt")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        self._use_custom = QCheckBox("Use custom prompt (uncheck to use default)", self)
        self._use_custom.setChecked(bool(current_custom))
        self._use_custom.toggled.connect(self._on_toggle)
        layout.addWidget(self._use_custom)

        self._tabs = QTabWidget(self)
        self._default = QPlainTextEdit(DEFAULT_PROMPT, self)
        self._default.setReadOnly(True)
        self._tabs.addTab(self._default, "Default (read-only)")

        self._custom = QPlainTextEdit(current_custom or DEFAULT_PROMPT, self)
        self._tabs.addTab(self._custom, "Custom")
        layout.addWidget(self._tabs, 1)

        hint = QLabel(
            "Available variables: " + ", ".join("{{" + v + "}}" for v in sorted(CUSTOM_VARIABLES)),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._on_toggle(self._use_custom.isChecked())

    def _on_toggle(self, checked: bool) -> None:
        self._tabs.setCurrentIndex(1 if checked else 0)

    def _save(self) -> None:
        if self._use_custom.isChecked():
            text = self._custom.toPlainText().strip()
            self.saved.emit(text or None)
        else:
            self.saved.emit(None)
        self.accept()
