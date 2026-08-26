"""Batch orchestrator — chains TranslationJobs for a queue of files."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from srtforge.translate.job import TranslationJob

log = logging.getLogger(__name__)


class TranslationQueue(QObject):
    """Runs a list of jobs sequentially.

    Signals:
      file_progress(file_index, total_files, file_name, chunk_done, chunk_total)
      file_finished(file_index, success, output_path)
      queue_finished(success_count, fail_count)
      log_line(level, text)
    """

    file_progress = Signal(int, int, str, int, int)
    file_finished = Signal(int, bool, str)
    queue_finished = Signal(int, int)
    log_line = Signal(str, str)

    def __init__(self, jobs: list[TranslationJob]) -> None:
        super().__init__()
        self._jobs = jobs
        self._index = 0
        self._success = 0
        self._fail = 0
        self._running = False
        self._current: TranslationJob | None = None

    def start(self) -> None:
        if self._running or not self._jobs:
            if not self._jobs:
                self.queue_finished.emit(0, 0)
            return
        self._running = True
        self._index = 0
        self._success = 0
        self._fail = 0
        self._run_next()

    def stop(self) -> None:
        if self._current is not None:
            self._current.stop()

    def _run_next(self) -> None:
        if self._index >= len(self._jobs):
            self._running = False
            self.queue_finished.emit(self._success, self._fail)
            return
        job = self._jobs[self._index]
        self._current = job
        job.log_line.connect(lambda level, text: self.log_line.emit(level, text))
        job.progress.connect(self._on_file_progress)
        job.finished.connect(self._on_file_finished)
        job.start()

    def _on_file_progress(
        self, chunk_done: int, chunk_total: int
    ) -> None:
        job = self._current
        if job is None:
            return
        self.file_progress.emit(
            self._index,
            len(self._jobs),
            job.source_path.name,
            chunk_done,
            chunk_total,
        )

    def _on_file_finished(self, success: bool, output_path: str) -> None:
        if success:
            self._success += 1
        else:
            self._fail += 1
        self.file_finished.emit(self._index, success, output_path)
        self._index += 1
        self._run_next()
