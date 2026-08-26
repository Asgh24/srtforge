"""Filesystem layout for SRTForge's persistent state.

Settings live in a per-user config directory. On Windows that's
``%APPDATA%/srtforge``. We try ``QStandardPaths`` first (most idiomatic)
and fall back to ``%APPDATA%`` so this module is importable *before*
``QApplication`` exists.
"""

from __future__ import annotations

import os
from pathlib import Path

_APP_DIR_NAME = "srtforge"


def config_dir() -> Path:
    """Return the user-specific config directory, creating it if needed."""
    # Prefer the Qt-canonical path (uses APPDATA on Windows, XDG on Linux).
    try:
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(QStandardPaths.AppConfigData)
        if base:
            path = Path(base) / _APP_DIR_NAME
            path.mkdir(parents=True, exist_ok=True)
            return path
    except Exception:  # noqa: BLE001 — never let path resolution crash the app
        pass

    # Fallback: %APPDATA% on Windows, ~/.config elsewhere.
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            path = Path(appdata) / _APP_DIR_NAME
        else:
            path = Path.home() / "AppData" / "Roaming" / _APP_DIR_NAME
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        path = Path(xdg) if xdg else Path.home() / ".config"
        path = path / _APP_DIR_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return config_dir() / "settings.json"


def cache_dir() -> Path:
    p = config_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = config_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
