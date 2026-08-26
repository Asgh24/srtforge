"""QThreadPool-based translation engine.

Layer breakdown:
  - ``LLMClient``    : pure HTTP, no Qt.
  - ``ChunkRunnable``: one API call for one chunk (QRunnable).
  - ``TranslationJob``: owns a QThreadPool, dispatches runnables,
                        aggregates signals, drives the sidecar.
  - ``TranslationQueue``: chains jobs for a batch of files.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from srtforge.config.profiles import APIProfile
from srtforge.srt.io import SubtitleEntry, save
from srtforge.translate.chunker import Chunk, chunk as build_chunks
from srtforge.translate.client import LLMClient
from srtforge.translate.models import ModelInfo
from srtforge.translate.persistence import (
    ChunkRecord,
    ChunkStatus,
    Sidecar,
    hash_file,
    load_sidecar,
    save_sidecar,
    sidecar_path,
)
from srtforge.translate.prompt import (
    DEFAULT_PROMPT,
    build_cue_payload,
    prompt_hash,
    render_prompt,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ChunkRunnable — one HTTP call, runs on a pool thread
# ---------------------------------------------------------------------------

class ChunkRunnable(QRunnable):
    """Carries one chunk through the API, emitting progress via signals.

    The signals are forwarded through the owning job's own signals so the
    GUI only connects to the job (single wiring point).
    """

    finished = Signal(int, dict)  # chunk_id -> {"status": ..., "translation": [...], "error": ...}
    chunk_started = Signal(int)

    def __init__(
        self,
        client: LLMClient,
        chunk: Chunk,
        *,
        prompt_template: str,
        source_lang: str,
        target_lang: str,
        temperature: float,
        max_tokens: int,
        stop_event: threading.Event,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._client = client
        self._chunk = chunk
        self._prompt_template = prompt_template
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._stop = stop_event

    def run(self) -> None:  # pragma: no cover — exercised via tests at higher level
        chunk_id = self._chunk.index
        self.chunk_started.emit(chunk_id)
        try:
            messages = self._build_messages()
            result = self._client.complete(
                messages,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                json_mode=True,
            )
            translation = _parse_translation(result.text)
            if translation is None:
                self.finished.emit(
                    chunk_id,
                    {
                        "status": "failed",
                        "error": "Model returned invalid JSON. See raw output in logs.",
                        "raw": result.text[:1000],
                    },
                )
                return
            self.finished.emit(
                chunk_id,
                {"status": "done", "translation": translation},
            )
        except Exception as exc:  # noqa: BLE001 — surface any worker error
            log.exception("Chunk %d failed", chunk_id)
            self.finished.emit(
                chunk_id,
                {"status": "failed", "error": str(exc)},
            )

    def _build_messages(self) -> list[dict]:
        prompt_text = render_prompt(
            self._prompt_template,
            source_lang=self._source_lang,
            target_lang=self._target_lang,
            chunk_index=self._chunk.index,
            chunk_count=self._estimate_chunk_count(),
            cues=build_cue_payload(self._chunk.entries),
        )
        return [
            {"role": "system", "content": "You translate subtitles to JSON."},
            {"role": "user", "content": prompt_text},
        ]

    def _estimate_chunk_count(self) -> int:
        # The prompt template uses {chunk_count}; we don't know it at
        # runnable-construction time reliably, so fall back to 1. The
        # chunker already rendered the real count; this only affects
        # the display string inside the prompt.
        return 1


def _parse_translation(raw_text: str) -> list[dict] | None:
    """Parse the model's JSON reply, tolerating markdown fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences.
        lines = text.splitlines()
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    translations = data.get("translations")
    if not isinstance(translations, list):
        return None
    out = []
    for item in translations:
        if not isinstance(item, dict):
            continue
        i = item.get("i")
        t = item.get("t")
        if i is not None and isinstance(t, str):
            out.append({"i": int(i), "t": t})
    return out if out else None


# ---------------------------------------------------------------------------
# TranslationJob — orchestrates one file
# ---------------------------------------------------------------------------

class TranslationJob(QObject):
    """Translates a single subtitle file in chunks.

    Signals (all cross-thread safe):
      progress(chunk_done: int, chunk_total: int)
      chunk_event(chunk_id: int, status: str, message: str)
      log_line(level: str, text: str)
      finished(success: bool, output_path: str | None)
    """

    progress = Signal(int, int)
    chunk_event = Signal(int, str, str)
    log_line = Signal(str, str)
    finished = Signal(bool, str)

    def __init__(
        self,
        source_path: Path,
        *,
        profile: APIProfile,
        model: ModelInfo,
        source_lang: str,
        target_lang: str,
        prompt_template: str | None = None,
        concurrency: int = 6,
        safety_margin: float = 0.85,
        temperature: float = 0.3,
        max_output_tokens: int = 1024,
        output_suffix: str = ".out.srt",
        timeout: float = 120.0,
    ) -> None:
        super().__init__()
        self.source_path = source_path
        self.profile = profile
        self.model = model
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.prompt_template = prompt_template or DEFAULT_PROMPT
        self.concurrency = max(1, concurrency)
        self.safety_margin = safety_margin
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.output_suffix = output_suffix
        self.timeout = timeout

        self._stop_event = threading.Event()
        self._pool: QThreadPool | None = None
        self._client = LLMClient(profile, model.id, timeout=timeout)
        self._sidecar: Sidecar | None = None
        self._chunks: list[Chunk] = []
        self._running = False

    # ---- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        # Load entries (blocking but fast; pysubs2 is pure python).
        from srtforge.srt.io import load as load_subs

        entries = load_subs(self.source_path)
        if not entries:
            self.log_line.emit("ERROR", "No subtitle cues found in file.")
            self.finished.emit(False, "")
            return

        self._chunks = build_chunks(
            entries,
            model=self.model,
            max_output_tokens=self.max_output_tokens,
            safety_margin=self.safety_margin,
            prompt_template=self.prompt_template,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )
        if not self._chunks:
            self.log_line.emit("ERROR", "Chunker produced zero chunks.")
            self.finished.emit(False, "")
            return

        sidecar = self._load_or_init_sidecar(entries)
        self._sidecar = sidecar

        # Reset in-flight/pending chunks that aren't done.
        todo = [
            c
            for c in self._chunks
            if self._chunk_status(c.index, sidecar) != ChunkStatus.DONE.value
        ]

        self.log_line.emit(
            "INFO",
            f"Loaded {len(entries)} cues, split into {len(self._chunks)} chunks; "
            f"{len(todo)} to translate.",
        )

        # Progress baseline: already-done chunks count.
        self.progress.emit(sidecar.done_count(), len(self._chunks))

        if not todo:
            self._write_output(entries, sidecar)
            self.finished.emit(True, str(self._output_path()))
            return

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(self.concurrency)

        for chunk in todo:
            runnable = ChunkRunnable(
                self._client,
                chunk,
                prompt_template=self.prompt_template,
                source_lang=self.source_lang,
                target_lang=self.target_lang,
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                stop_event=self._stop_event,
            )
            # Forward chunk signals to the job's signals.
            runnable.chunk_started.connect(
                lambda cid: self._on_chunk_started(cid)
            )
            runnable.finished.connect(lambda cid, payload: self._on_chunk_done(cid, payload))
            self._pool.start(runnable)

        # The pool auto-deletes runnables; we watch for idle via a timer-ish
        # poll. QThreadPool has no finished signal in Qt6 for the pool
        # itself, so we track a counter.
        self._pending_count = len(todo)
        self._done_count = 0

    # ---- internals -----------------------------------------------------

    def _load_or_init_sidecar(self, entries: list[SubtitleEntry]) -> Sidecar:
        path = sidecar_path(self.source_path)
        existing = load_sidecar(path)
        if existing is not None and existing.source_sha256 == hash_file(self.source_path):
            return existing
        # New sidecar, or hash mismatch → fresh state.
        sidecar = Sidecar(
            source_sha256=hash_file(self.source_path),
            source_path=str(self.source_path),
            model_id=self.model.id,
            prompt_hash=prompt_hash(self.prompt_template),
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            created_at=time.time(),
        )
        # Preserve chunk indices from the chunker (same file → same layout).
        for chunk in self._chunks:
            sidecar.chunks.append(
                ChunkRecord(id=chunk.index, indices=chunk.indices)
            )
        save_sidecar(path, sidecar)
        return sidecar

    def _chunk_status(self, chunk_id: int, sidecar: Sidecar) -> str:
        for c in sidecar.chunks:
            if c.id == chunk_id:
                return c.status
        return ChunkStatus.PENDING.value

    def _on_chunk_started(self, chunk_id: int) -> None:
        if self._sidecar is not None:
            for c in self._sidecar.chunks:
                if c.id == chunk_id:
                    c.status = ChunkStatus.IN_FLIGHT.value
                    c.attempts += 1
            save_sidecar(sidecar_path(self.source_path), self._sidecar)
        self.log_line.emit("INFO", f"[Chunk {chunk_id}] sending to {self.model.id}")

    def _on_chunk_done(self, chunk_id: int, payload: dict) -> None:
        self._done_count += 1
        status = payload.get("status")
        sidecar = self._sidecar
        if sidecar is not None:
            for c in sidecar.chunks:
                if c.id == chunk_id:
                    c.status = status
                    if status == "done":
                        c.translation = payload.get("translation", [])
                        c.completed_at = time.time()
                    else:
                        c.error = payload.get("error", "")
            save_sidecar(sidecar_path(self.source_path), sidecar)

        if status == "done":
            self.log_line.emit(
                "INFO", f"[Chunk {chunk_id}] done ({len(payload.get('translation', []))} cues)"
            )
        else:
            self.log_line.emit(
                "ERROR", f"[Chunk {chunk_id}] FAILED: {payload.get('error', '')}"
            )

        done = sidecar.done_count() if sidecar else self._done_count
        self.progress.emit(done, len(self._chunks))
        self.chunk_event.emit(chunk_id, status, "")

        if self._done_count >= self._pending_count:
            self._finish_job()

    def _finish_job(self) -> None:
        sidecar = self._sidecar
        if sidecar is not None and sidecar.failed_count() == 0:
            entries = load_subs(self.source_path)
            self._apply_translations(entries, sidecar)
            out = self._output_path()
            save(out, entries)
            self.log_line.emit("INFO", f"Saved translated file: {out}")
            self.finished.emit(True, str(out))
        else:
            # Some chunks failed — don't write output; user can retry.
            self.finished.emit(False, "")

    def _apply_translations(
        self, entries: list[SubtitleEntry], sidecar: Sidecar
    ) -> None:
        # Build a map: cue index -> translated text (from every done chunk).
        translation_map: dict[int, str] = {}
        for chunk_rec in sidecar.chunks:
            if chunk_rec.status != ChunkStatus.DONE.value:
                continue
            for item in chunk_rec.translation:
                translation_map[int(item["i"])] = item["t"]
        for entry in entries:
            if entry.index in translation_map:
                entry.translated = translation_map[entry.index]

    def _output_path(self) -> Path:
        return self.source_path.with_suffix(self.output_suffix)

    def stop(self) -> None:
        self._stop_event.set()
        if self._pool is not None:
            self._pool.clear()  # don't start queued-but-not-running runnables
