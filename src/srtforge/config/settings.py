"""Settings persistence — JSON file under the user config directory."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from srtforge.config.paths import settings_file
from srtforge.config.profiles import APIProfile

log = logging.getLogger(__name__)

_SETTINGS_VERSION = 1


@dataclass
class Settings:
    """Top-level user settings.

    Serialised as JSON in ``settings.json``. The schema is versioned via
    ``_SETTINGS_VERSION`` so future migrations stay predictable.
    """

    # Profile selection
    active_profile_id: str | None = None
    profiles: list[APIProfile] = field(default_factory=list)

    # Translation defaults
    concurrency: int = 6
    safety_margin: float = 0.85
    default_target_lang: str = "English"
    default_source_lang: str = "auto"  # "auto" or Language code
    custom_prompt: str | None = None
    temperature: float = 0.3
    request_timeout: float = 120.0
    max_output_tokens: int = 1024  # per chunk; hard clamp regardless of model

    # UI
    theme: str = "dark"  # "dark" | "light" | "system"
    log_level: str = "INFO"

    # History
    recent_files: list[str] = field(default_factory=list)
    last_output_dir: str | None = None

    # Advanced
    chunk_overlap_cues: int = 0  # off by default; 1-2 helps with continuity

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["__version__"] = _SETTINGS_VERSION
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        known = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in data.items() if k in known}
        profiles_raw = clean.get("profiles", [])
        clean["profiles"] = [APIProfile.from_dict(p) for p in profiles_raw]
        return cls(**clean)

    def active_profile(self) -> APIProfile | None:
        if not self.active_profile_id:
            return None
        for p in self.profiles:
            if p.id == self.active_profile_id:
                return p
        return None

    def upsert_profile(self, profile: APIProfile) -> None:
        for i, p in enumerate(self.profiles):
            if p.id == profile.id:
                self.profiles[i] = profile
                return
        self.profiles.append(profile)
        if self.active_profile_id is None:
            self.active_profile_id = profile.id

    def remove_profile(self, profile_id: str) -> None:
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        if self.active_profile_id == profile_id:
            self.active_profile_id = self.profiles[0].id if self.profiles else None


class SettingsStore:
    """Thin wrapper that owns the Settings instance and a save() method.

    The intent is to keep all disk I/O here so the rest of the app
    doesn't need to know about file paths.
    """

    def __init__(self, data: Settings, path: Path | None = None) -> None:
        self.data = data
        self._path = path or settings_file()

    @classmethod
    def load(cls, path: Path | None = None) -> "SettingsStore":
        target = path or settings_file()
        if not target.exists():
            log.info("No settings file at %s; using defaults", target)
            return cls(Settings(), target)
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            settings = Settings.from_dict(raw)
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            log.warning("Failed to load settings (%s); using defaults", exc)
            return cls(Settings(), target)
        return cls(settings, target)

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self.data.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            log.error("Could not save settings: %s", exc)
