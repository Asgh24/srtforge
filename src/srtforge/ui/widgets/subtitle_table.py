"""SubtitleTable — before/after view of cues for the currently-selected file."""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from srtforge.srt.model import SubtitleEntry


class _SubtitleModel(QAbstractTableModel):
    HEADERS = ["#", "Time", "Source", "Translation"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[SubtitleEntry] = []

    def set_entries(self, entries: list[SubtitleEntry]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 4

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self.HEADERS[section]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(entry.index)
            if col == 1:
                return f"{_fmt_ms(entry.start_ms)} → {_fmt_ms(entry.end_ms)}"
            if col == 2:
                return entry.text
            if col == 3:
                return entry.translated or ""
        if role == Qt.ForegroundRole and col == 3:
            if entry.translated:
                return QColor("#34d399")
        return None


def _fmt_ms(ms: int) -> str:
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:02d}:{s:02d}.{ms:03d}"


class SubtitleTable(QWidget):
    file_changed = Signal(int)  # chunk_id when user picks a different file

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableView(self)
        self._model = _SubtitleModel(self)
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(1, 140)
        layout.addWidget(self._table)

    def set_entries(self, entries: list[SubtitleEntry]) -> None:
        self._model.set_entries(entries)
        if entries:
            self._table.resizeColumnToContents(2)
