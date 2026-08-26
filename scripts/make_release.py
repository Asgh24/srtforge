#!/usr/bin/env python3
"""Build a release .exe and stage it under dist/."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    print("Installing build deps…")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=False,
    )
    print("Building with PyInstaller…")
    proc = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "srtforge.spec", "--clean", "--noconfirm"],
        cwd=ROOT,
    )
    if proc.returncode != 0:
        print("Build failed.")
        return proc.returncode
    exe = ROOT / "dist" / "SRTForge" / "SRTForge.exe"
    if exe.exists():
        print(f"OK: {exe}")
        return 0
    print("Build finished but executable not found.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
