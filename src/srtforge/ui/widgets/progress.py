"""BeautifulProgressBar — animated bar with a chunk-grid overlay.

Two layers:
  1. The standard QProgressBar underneath (gives us the OS look for free).
  2. A QWidget overlay drawn on top, painting one cell per chunk so the
     user can see *which* chunks are done, in-flight, failed, pending.

This is a hybrid because Qt's QProgressBar handles the gradient/timing
for us; we only add the chunk grid.
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QVBoxLayout, QWidget


class _ChunkGrid(QWidget):
    """Draws one cell per chunk with colour-coded state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumHeight(18)
        self._total = 0
        self._done = 0
        self._failed: set[int] = set()
        self._inflight: set[int] = set()

    def set_total(self, total: int) -> None:
        self._total = max(0, total)
        self._done = 0
        self._failed.clear()
        self._inflight.clear()
        self.update()

    def mark_done(self, count: int) -> None:
        self._done = count
        self.update()

    def mark_failed(self, chunk_id: int) -> None:
        self._failed.add(chunk_id)
        self.update()

    def mark_inflight(self, chunk_id: int) -> None:
        self._inflight.add(chunk_id)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401
        if self._total <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        n = self._total
        gap = 2
        cell_w = max(4, (rect.width() - gap * (n - 1)) // n)
        cell_h = rect.height()
        x = rect.x()
        accent = QColor(self.palette().highlight().color())
        muted = QColor(self.palette().mid().color())
        error = QColor(self.palette().shadow().color())
        for i in range(n):
            cell = QRect(x, rect.y(), cell_w, cell_h)
            if i < self._done:
                painter.fillRect(cell, accent)
            elif (i + 1) in self._failed:
                painter.fillRect(cell, error)
            elif (i + 1) in self._inflight:
                # Pulsing-ish — just a slightly darker accent.
                c = QColor(accent)
                c.setAlpha(180)
                painter.fillRect(cell, c)
            else:
                painter.fillRect(cell, muted)
            x += cell_w + gap
        painter.end()


class BeautifulProgressBar(QWidget):
    """A QProgressBar with an overlaid chunk grid and an ETA label."""

    eta_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)
        self._bar = QProgressBar(self)
        self._bar.setRange(0, 1)
        self._bar.setValue(0)
        self._bar.setFormat("%v / %m chunks  (%p%)")
        self._bar.setObjectName("chunkProgress")
        self._grid = _ChunkGrid(self)
        self._grid.set_total(0)
        # Stack the grid on top of the bar by using a container.
        self._stack = QWidget(self)
        self._stack.setMinimumHeight(self._bar.sizeHint().height())
        sl = QVBoxLayout(self._stack)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self._bar)
        self._grid.setParent(self._stack)
        self._grid.setGeometry(self._stack.rect())
        self._stack.resizeEvent = self._on_stack_resize  # type: ignore[assignment]
        bar_row.addWidget(self._stack, 1)
        layout.addLayout(bar_row)

        self._eta_label_text = ""
        self._start_ts = 0.0

    def _on_stack_resize(self, event) -> None:  # pragma: no cover — UI plumbing
        self._grid.setGeometry(0, 0, self._stack.width(), self._stack.height())
        QWidget.resizeEvent(self._stack, event)

    # ---- public API ----------------------------------------------------

    def set_total(self, total: int) -> None:
        self._bar.setRange(0, max(1, total))
        self._bar.setValue(0)
        self._grid.set_total(total)
        self._start_ts = 0.0
        self.eta_changed.emit("")

    def set_done(self, done: int) -> None:
        import time
        if self._start_ts == 0.0 and done > 0:
            self._start_ts = time.time()
        self._bar.setValue(done)
        self._grid.mark_done(done)
        if done > 0 and self._bar.maximum() > 0:
            elapsed = time.time() - self._start_ts if self._start_ts else 0
            rate = done / max(elapsed, 0.001)
            remaining = self._bar.maximum() - done
            eta = remaining / max(rate, 0.001)
            self.eta_changed.emit(self._format_eta(eta))
        else:
            self.eta_changed.emit("")

    def mark_chunk_inflight(self, chunk_id: int) -> None:
        self._grid.mark_inflight(chunk_id)

    def mark_chunk_failed(self, chunk_id: int) -> None:
        self._grid.mark_failed(chunk_id)

    @staticmethod
    def _format_eta(seconds: float) -> str:
        if seconds < 0 or seconds > 24 * 3600:
            return ""
        if seconds < 60:
            return f"ETA {int(seconds)}s"
        m, s = divmod(int(seconds), 60)
        if m < 60:
            return f"ETA {m}m {s:02d}s"
        h, m = divmod(m, 60)
        return f"ETA {h}h {m:02d}m"
