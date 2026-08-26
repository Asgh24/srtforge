"""Per-file sidecar state — resume, retry, audit.

We write ``<name>.srtforge.json`` next to the source SRT after every
chunk completion so a crash mid-translation doesn't lose progress. The
sidecar is the single source of truth for what is and isn't done.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SIDECAR_VERSION = 1
SIDECAR_SUFFIX = ".srtforge.json"


class ChunkStatus(str, Enum):
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ChunkRecord:
    id: int
    indices: str
    status: str = ChunkStatus.PENDING.value
    translation: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    attempts: int = 0
    completed_at: float = 0.0


@dataclass
class Sidecar:
    version: int = SIDECAR_VERSION
    source_sha256: str = ""
    source_path: str = ""
    model_id: str = ""
    prompt_hash: str = ""
    source_lang: str = "auto"
    target_lang: str = "English"
    created_at: float = 0.0
    updated_at: float = 0.0
    chunks: list[ChunkRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sidecar":
        chunks_raw = data.get("chunks", [])
        chunks = []
        for c in chunks_raw:
            if not isinstance(c, dict):
                continue
            known = {f for f in ChunkRecord.__dataclass_fields__}
            clean = {k: v for k, v in c.items() if k in known}
            chunks.append(ChunkRecord(**clean))
        data_clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        data_clean["chunks"] = chunks
        # Forward compat: ignore unknown version, treat as v1.
        return cls(**data_clean)

    # ---- convenience queries ------------------------------------------

    def pending_ids(self) -> list[int]:
        return [
            c.id
            for c in self.chunks
            if c.status in (ChunkStatus.PENDING.value, ChunkStatus.FAILED.value)
        ]

    def done_count(self) -> int:
        return sum(1 for c in self.chunks if c.status == ChunkStatus.DONE.value)

    def failed_count(self) -> int:
        return sum(1 for c in self.chunks if c.status == ChunkStatus.FAILED.value)

    def total_count(self) -> int:
        return len(self.chunks)

    def completion_ratio(self) -> float:
        total = self.total_count()
        if total == 0:
            return 0.0
        return self.done_count() / total

    def upsert_chunk(self, record: ChunkRecord) -> None:
        for i, c in enumerate(self.chunks):
            if c.id == record.id:
                self.chunks[i] = record
                return
        self.chunks.append(record)


def hash_file(path: Path) -> str:
    """SHA-256 of a file's bytes — used to detect source changes on resume."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def sidecar_path(source: Path) -> Path:
    return source.with_suffix("").with_name(source.name + SIDECAR_SUFFIX)


def load_sidecar(path: Path) -> Sidecar | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Sidecar.from_dict(data)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not load sidecar %s: %s", path, exc)
        return None


def save_sidecar(path: Path, sidecar: Sidecar) -> None:
    sidecar.updated_at = time.time()
    try:
        path.write_text(
            json.dumps(sidecar.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        log.error("Failed to write sidecar %s: %s", path, exc)
