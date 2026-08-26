# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SRTForge.

Build:
    pyinstaller srtforge.spec
Output: dist/SRTForge/SRTForge.exe (onedir) — copy that folder anywhere.
"""

from pathlib import Path

# SPECPATH is only defined when the spec is run directly by PyInstaller.
project_root = Path(SPECPATH).parent
src_dir = project_root / "src"
main_script = (src_dir / "srtforge" / "__main__.py").resolve()

a = Analysis(
    [str(main_script)],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[(str(src_dir / "srtforge" / "resources"), "srtforge/resources")],
    hiddenimports=[
        "pysubs2",
        "pysubs2.formats",
        "requests",
        "requests.packages.urllib3.util.retry",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "email",
        "sqlite3",
        "pydoc_data",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SRTForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
