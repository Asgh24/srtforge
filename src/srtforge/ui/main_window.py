"""MainWindow — single primary window that ties everything together."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from srtforge import __app_name__
from srtforge.config.profiles import APIProfile
from srtforge.config.settings import SettingsStore
from srtforge.srt.io import load as load_subs
from srtforge.translate.languages import all_choices, AUTO
from srtforge.translate.models import ModelInfo, list_models
from srtforge.translate.queue import TranslationQueue
from srtforge.translate.job import TranslationJob
from srtforge.ui.dialogs.settings_dialog import SettingsDialog
from srtforge.ui.theme import apply_theme
from srtforge.ui.widgets.api_profiles_dialog import APIProfilesDialog
from srtforge.ui.widgets.log_view import LogView
from srtforge.ui.widgets.progress import BeautifulProgressBar
from srtforge.ui.widgets.subtitle_table import SubtitleTable

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self._settings = settings
        self.setWindowTitle(__app_name__)
        self.resize(1280, 820)

        # State that the rest of the app reads.
        self._files: list[Path] = []
        self._active_models: dict[str, list[ModelInfo]] = {}  # profile_id -> models
        self._active_model_info: ModelInfo | None = None
        self._queue: TranslationQueue | None = None

        self._build_ui()
        self._build_menu()
        self._populate_languages()
        self._populate_profiles()
        self._refresh_models_async()

    # ---- UI construction ----------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Toolbar
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        self._tb_add = QAction("Add SRT…", self)
        self._tb_add.triggered.connect(self._on_add_files)
        tb.addAction(self._tb_add)
        self._tb_clear = QAction("Clear queue", self)
        self._tb_clear.triggered.connect(self._on_clear_queue)
        tb.addAction(self._tb_clear)
        tb.addSeparator()
        self._tb_start = QAction("Start", self)
        self._tb_start.setShortcut(QKeySequence("Ctrl+Return"))
        self._tb_start.triggered.connect(self._on_start)
        tb.addAction(self._tb_start)
        self._tb_stop = QAction("Stop", self)
        self._tb_stop.triggered.connect(self._on_stop)
        tb.addAction(self._tb_stop)
        tb.addSeparator()
        self._tb_settings = QAction("Settings", self)
        self._tb_settings.triggered.connect(self._on_settings)
        tb.addAction(self._tb_settings)
        self._tb_profiles = QAction("API Profiles", self)
        self._tb_profiles.triggered.connect(self._on_profiles)
        tb.addAction(self._tb_profiles)

        # Queue
        self._queue_table = QTableWidget(0, 4, self)
        self._queue_table.setHorizontalHeaderLabels(["#", "File", "Status", "Progress"])
        self._queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._queue_table.verticalHeader().setVisible(False)
        self._queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._queue_table.itemSelectionChanged.connect(self._on_queue_row_changed)
        self._queue_table.setMaximumHeight(160)
        root.addWidget(self._queue_table)

        # Progress
        self._progress = BeautifulProgressBar(self)
        root.addWidget(self._progress)

        # Splitter: preview on left, log on right
        splitter = QSplitter(Qt.Horizontal, self)
        self._subtitle_table = SubtitleTable(splitter)
        self._log = LogView(splitter)
        splitter.addWidget(self._subtitle_table)
        splitter.addWidget(self._log)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 400])
        root.addWidget(splitter, 1)

        # Config bar (bottom)
        cfg = QHBoxLayout()
        cfg.setSpacing(8)
        cfg.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox(self)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        cfg.addWidget(self._profile_combo)
        cfg.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox(self)
        self._model_combo.setEditable(True)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        cfg.addWidget(self._model_combo, 1)
        self._refresh_models_btn = QPushButton("Refresh", self)
        self._refresh_models_btn.clicked.connect(self._refresh_models_async)
        cfg.addWidget(self._refresh_models_btn)
        cfg.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox(self)
        cfg.addWidget(self._source_combo)
        cfg.addWidget(QLabel("Target:"))
        self._target_combo = QComboBox(self)
        cfg.addWidget(self._target_combo)
        root.addLayout(cfg)

        # Status bar
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._eta_label = QLabel("", self)
        sb.addPermanentWidget(self._eta_label)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self._tb_add)
        file_menu.addAction(self._tb_clear)
        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu = menubar.addMenu("&View")
        toggle_theme = QAction("Toggle theme", self)
        toggle_theme.setShortcut(QKeySequence("Ctrl+T"))
        toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme)

        help_menu = menubar.addMenu("&Help")
        about = QAction("&About", self)
        about.triggered.connect(self._on_about)
        help_menu.addAction(about)

    # ---- data population -----------------------------------------------

    def _populate_languages(self) -> None:
        for combo in (self._source_combo, self._target_combo):
            combo.clear()
            combo.addItems(all_choices())
        # Sensible defaults
        self._source_combo.setCurrentText(AUTO)
        self._target_combo.setCurrentText(self._settings.data.default_target_lang)

    def _populate_profiles(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for p in self._settings.data.profiles:
            self._profile_combo.addItem(p.name, p.id)
        active_id = self._settings.data.active_profile_id
        if active_id:
            for i, p in enumerate(self._settings.data.profiles):
                if p.id == active_id:
                    self._profile_combo.setCurrentIndex(i)
                    break
        self._profile_combo.blockSignals(False)

    def _active_profile(self) -> APIProfile | None:
        return self._settings.data.active_profile()

    def _refresh_models_async(self) -> None:
        profile = self._active_profile()
        if profile is None:
            self._model_combo.clear()
            return
        if not profile.models_cache:
            try:
                models = list_models(profile.base_url, profile.api_key)
            except Exception as exc:  # noqa: BLE001
                self._log.append_log("ERROR", f"Failed to fetch /models: {exc}")
                models = []
            profile.models_cache = [m.to_dict_compat() for m in models] if hasattr(models[0], "to_dict_compat") else []
            # Workaround: list_models returns ModelInfo objects; convert to dict
            from dataclasses import asdict

            profile.models_cache = [asdict(m) for m in models]
            self._settings.save()
        # Render to combobox
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        from srtforge.translate.models import ModelInfo

        for m in profile.models_cache:
            try:
                mi = ModelInfo(**{k: m.get(k) for k in ("id", "name", "context_length", "max_output_tokens") if k in m})
            except Exception:  # noqa: BLE001
                continue
            label = f"{m.get('name', m.get('id', '?'))}  ·  ctx={m.get('context_length', 0)}"
            self._model_combo.addItem(label, m.get("id"))
        self._model_combo.blockSignals(False)
        if self._model_combo.count() > 0:
            self._model_combo.setCurrentIndex(0)
            self._on_model_changed(0)

    # ---- handlers ------------------------------------------------------

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add SRT files", "", "Subtitle files (*.srt);;All files (*)"
        )
        for p in paths:
            pp = Path(p)
            if pp not in self._files:
                self._files.append(pp)
        self._rebuild_queue_table()
        self._save_recent()

    def _on_clear_queue(self) -> None:
        self._files.clear()
        self._rebuild_queue_table()
        self._subtitle_table.set_entries([])

    def _on_profile_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._settings.data.profiles):
            return
        self._settings.data.active_profile_id = self._settings.data.profiles[idx].id
        self._settings.save()
        self._refresh_models_async()

    def _on_model_changed(self, idx: int) -> None:
        if idx < 0:
            return
        model_id = self._model_combo.itemData(idx) or self._model_combo.currentText()
        profile = self._active_profile()
        if profile is None or not model_id:
            return
        from srtforge.translate.models import ModelInfo

        for m in profile.models_cache:
            if m.get("id") == model_id:
                self._active_model_info = ModelInfo(
                    id=m.get("id", ""),
                    name=m.get("name", m.get("id", "")),
                    context_length=int(m.get("context_length", 0)) or 8192,
                    max_output_tokens=m.get("max_output_tokens"),
                )
                return

    def _on_queue_row_changed(self) -> None:
        row = self._queue_table.currentRow()
        if row < 0 or row >= len(self._files):
            self._subtitle_table.set_entries([])
            return
        try:
            entries = load_subs(self._files[row])
            self._subtitle_table.set_entries(entries)
        except Exception as exc:  # noqa: BLE001
            self._log.append_log("ERROR", f"Failed to load {self._files[row].name}: {exc}")
            self._subtitle_table.set_entries([])

    def _on_start(self) -> None:
        if not self._files:
            QMessageBox.information(self, "SRTForge", "Add at least one SRT file first.")
            return
        profile = self._active_profile()
        if profile is None or not profile.api_key:
            QMessageBox.warning(
                self, "SRTForge", "No active API profile with a key. Open API Profiles."
            )
            return
        if self._active_model_info is None:
            QMessageBox.warning(self, "SRTForge", "Pick a model first.")
            return
        jobs: list[TranslationJob] = []
        for f in self._files:
            job = TranslationJob(
                f,
                profile=profile,
                model=self._active_model_info,
                source_lang=self._source_combo.currentText(),
                target_lang=self._target_combo.currentText(),
                prompt_template=self._settings.data.custom_prompt,
                concurrency=self._settings.data.concurrency,
                safety_margin=self._settings.data.safety_margin,
                temperature=self._settings.data.temperature,
                max_output_tokens=self._settings.data.max_output_tokens,
                timeout=self._settings.data.request_timeout,
            )
            jobs.append(job)
        self._queue = TranslationQueue(jobs)
        self._queue.log_line.connect(self._on_log)
        self._queue.file_progress.connect(self._on_file_progress)
        self._queue.file_finished.connect(self._on_file_finished)
        self._queue.queue_finished.connect(self._on_queue_finished)
        self._progress.set_total(0)
        self._log.append_log("INFO", f"Starting queue of {len(jobs)} file(s)…")
        self._queue.start()

    def _on_stop(self) -> None:
        if self._queue is not None:
            self._queue.stop()
            self._log.append_log("WARN", "Stop requested.")

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self) -> None:
        apply_theme(self.app_instance(), self._settings.data.theme)

    def _on_profiles(self) -> None:
        dlg = APIProfilesDialog(self._settings, self)
        dlg.exec()
        self._populate_profiles()
        self._refresh_models_async()

    def _on_about(self) -> None:
        from srtforge import __version__

        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h3>{__app_name__} {__version__}</h3>"
            "<p>Desktop subtitle translator for SRT files.</p>"
            "<p>Uses OpenAI-compatible LLM APIs (OpenRouter, etc.)</p>"
            "<p>MIT License</p>",
        )

    def _on_toggle_theme_action(self) -> None:
        self._toggle_theme()

    def _toggle_theme(self) -> None:
        new = "light" if self._settings.data.theme == "dark" else "dark"
        self._settings.data.theme = new
        self._settings.save()
        apply_theme(self.app_instance(), new)

    def _on_log(self, level: str, text: str) -> None:
        self._log.append_log(level, text)

    def _on_file_progress(
        self,
        file_index: int,
        total_files: int,
        file_name: str,
        chunk_done: int,
        chunk_total: int,
    ) -> None:
        if file_index < self._queue_table.rowCount():
            status = self._queue_table.item(file_index, 2)
            if status is None:
                status = QTableWidgetItem("")
                self._queue_table.setItem(file_index, 2, status)
            status.setText(f"Translating  {chunk_done}/{chunk_total}")
            prog = self._queue_table.item(file_index, 3)
            if prog is None:
                prog = QTableWidgetItem("")
                self._queue_table.setItem(file_index, 3, prog)
            if chunk_total > 0:
                prog.setText(f"{int(100 * chunk_done / chunk_total)}%")
        # Update global progress as a sum of all files
        # (We use a single rolling aggregate; for a polished UI you'd
        # compute the cumulative chunks across all files. Keeping simple.)
        self._progress.set_total(max(self._progress._bar.maximum(), chunk_total))
        self._progress.set_done(chunk_done)

    def _on_file_finished(self, file_index: int, success: bool, output_path: str) -> None:
        if file_index < self._queue_table.rowCount():
            status = self._queue_table.item(file_index, 2)
            if status is None:
                status = QTableWidgetItem("")
                self._queue_table.setItem(file_index, 2, status)
            status.setText("Done ✓" if success else "Stopped / errors")
        if success and output_path:
            self._log.append_log("SUCCESS", f"Wrote {output_path}")

    def _on_queue_finished(self, success_count: int, fail_count: int) -> None:
        self._log.append_log(
            "INFO", f"Queue finished: {success_count} succeeded, {fail_count} failed."
        )
        self._status_message(f"Done: {success_count} ok / {fail_count} failed")

    def _rebuild_queue_table(self) -> None:
        self._queue_table.setRowCount(len(self._files))
        for i, f in enumerate(self._files):
            self._queue_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._queue_table.setItem(i, 1, QTableWidgetItem(f.name))
            self._queue_table.setItem(i, 2, QTableWidgetItem("Queued"))
            self._queue_table.setItem(i, 3, QTableWidgetItem(""))

    def _save_recent(self) -> None:
        self._settings.data.recent_files = [str(p) for p in self._files[-20:]]
        self._settings.save()

    def _status_message(self, text: str) -> None:
        self.statusBar().showMessage(text, 5000)

    def app_instance(self):  # convenience for theme
        from PySide6.QtWidgets import QApplication

        return QApplication.instance()

    def closeEvent(self, event) -> None:  # noqa: D401
        if self._queue is not None:
            self._queue.stop()
        self._settings.save()
        super().closeEvent(event)
