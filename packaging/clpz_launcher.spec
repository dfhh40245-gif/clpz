# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the CLPZ desktop launcher (windowed exe).
# Build:  python -m PyInstaller packaging/clpz_launcher.spec --noconfirm --distpath packaging/dist --workpath packaging/build
# Output: packaging/dist/clpz_launcher/CLPZ.exe

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # SPECPATH = the packaging/ dir

hiddenimports = [
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.cef",
]

a = Analysis(
    [str(ROOT / "desktop" / "frozen_launcher.py")],
    pathex=[str(ROOT / "desktop")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "boto3", "botocore", "s3transfer",
        "tkinter", "matplotlib", "pytest", "IPython",
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
    name="CLPZ",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # windowed app — no console on launch
    disable_windowed_traceback=False,
    icon=None,           # add packaging/clpz.ico here when the icon is ready
)
