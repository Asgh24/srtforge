"""API profiles dialog — CRUD for LLM endpoint configurations."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from srtforge.config.profiles import APIProfile, _new_id
from srtforge.config.settings import SettingsStore


class APIProfilesDialog(QDialog):
    def __init__(
        self,
        settings: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("API Profiles")
        self.resize(640, 480)

        layout = QVBoxLayout(self)

        self._list = QListWidget(self)
        self._list.itemSelectionChanged.connect(self._load_selected)
        layout.addWidget(self._list, 1)

        form = QFormLayout()
        self._name = QLineEdit(self)
        self._url = QLineEdit(self)
        self._url.setPlaceholderText("https://openrouter.ai/api/v1")
        self._key = QLineEdit(self)
        self._key.setEchoMode(QLineEdit.Password)
        self._referer = QLineEdit(self)
        self._app_title = QLineEdit(self)
        self._app_title.setText("SRTForge")
        self._anthropic = QCheckBox("Use Anthropic native endpoint", self)
        form.addRow("Name", self._name)
        form.addRow("Base URL", self._url)
        form.addRow("API Key", self._key)
        form.addRow("HTTP-Referer (optional)", self._referer)
        form.addRow("X-Title (optional)", self._app_title)
        form.addRow("", self._anthropic)
        layout.addLayout(form)

        btns = QHBoxLayout()
        new_btn = QPushButton("New", self)
        new_btn.clicked.connect(self._new_profile)
        del_btn = QPushButton("Delete", self)
        del_btn.clicked.connect(self._delete_profile)
        btns.addWidget(new_btn)
        btns.addWidget(del_btn)
        btns.addStretch(1)
        layout.addLayout(btns)

        box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        active_id = self._settings.data.active_profile_id
        for p in self._settings.data.profiles:
            item_text = p.display_summary()
            if p.id == active_id:
                item_text = "★ " + item_text
            self._list.addItem(item_text)
            if p.id == active_id:
                self._list.setCurrentRow(self._list.count() - 1)
        self._list.blockSignals(False)
        if self._list.currentRow() >= 0:
            self._load_selected()

    def _current_profile(self) -> APIProfile | None:
        idx = self._list.currentRow()
        if idx < 0 or idx >= len(self._settings.data.profiles):
            return None
        return self._settings.data.profiles[idx]

    def _load_selected(self) -> None:
        p = self._current_profile()
        if p is None:
            return
        self._name.setText(p.name)
        self._url.setText(p.base_url)
        self._key.setText(p.api_key)
        self._referer.setText(p.referer)
        self._app_title.setText(p.app_title)
        self._anthropic.setChecked(p.anthropic_native)
        self._settings.data.active_profile_id = p.id

    def _new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name.strip():
            return
        p = APIProfile(
            name=name.strip(),
            base_url=self._url.text().strip() or "https://openrouter.ai/api/v1",
            api_key="",
        )
        self._settings.data.upsert_profile(p)
        self._settings.save()
        self._refresh_list()

    def _delete_profile(self) -> None:
        p = self._current_profile()
        if p is None:
            return
        ok = QMessageBox.question(
            self,
            "Delete profile",
            f"Delete profile '{p.name}'?",
        )
        if ok != QMessageBox.Yes:
            return
        self._settings.data.remove_profile(p.id)
        self._settings.save()
        self._refresh_list()

    def _save(self) -> None:
        p = self._current_profile()
        if p is None:
            self.accept()
            return
        p.name = self._name.text().strip() or p.name
        p.base_url = self._url.text().strip() or p.base_url
        p.api_key = self._key.text().strip()
        p.referer = self._referer.text().strip()
        p.app_title = self._app_title.text().strip() or "SRTForge"
        p.anthropic_native = self._anthropic.isChecked()
        # Invalidate the model cache so a re-fetch picks up changes.
        p.models_cache = []
        p.models_cached_at = 0.0
        self._settings.save()
        self.accept()
