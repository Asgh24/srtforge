# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SRTForge.

Build:
    pyinstaller srtforge.spec
Output: dist/SRTForge/SRTForge.exe (onedir) — copy that folder anywhere.
"""

from pathlib import Path

# In PyInstaller, SPECPATH is the DIRECTORY containing the spec file,
# not the file path itself.
project_root = Path(SPECPATH)
src_dir = project_root / "src"
main_script = (src_dir / "srtforge" / "__main__.py").resolve()
resources_dir = src_dir / "srtforge" / "resources"

# Only add datas if the resources dir has tracked content; PyInstaller
# errors on an empty or missing source directory.
datas: list[tuple[str, str]] = []
if resources_dir.exists() and any(resources_dir.iterdir()):
    datas.append((str(resources_dir), "srtforge/resources"))

a = Analysis(
    [str(main_script)],
    pathex=[str(src_dir)],
    binaries=[],
    datas=datas,
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
