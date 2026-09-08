# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the CLPZ packaged server executable.
# Build:  python -m PyInstaller packaging/clpz_server.spec --noconfirm --distpath packaging/dist --workpath packaging/build
# Output: packaging/dist/clpz_server/clpz_server.exe  (onedir mode)

import os
from pathlib import Path

import faster_whisper  # noqa: E402  (datas needs its asset path)

ROOT = Path(SPECPATH).resolve().parent  # SPECPATH = the packaging/ dir
BACKEND = ROOT / "backend"

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn",
    "main",
    "config",
    "database",
    "auth",
    "credits",
    "email_service",
    "jobs",
    "proc",
    "clpz_server",
    "pipeline",
    "pipeline.analyzer",
    "pipeline.captions",
    "pipeline.cutter",
    "pipeline.downloader",
    "pipeline.srt_parser",
    "pipeline.transcriber",
    "faster_whisper",
    "faster_whisper.audio",
    "faster_whisper.feature_extractor",
    "faster_whisper.tokenizer",
    "faster_whisper.transcribe",
    "faster_whisper.utils",
    "faster_whisper.vad",
    "ctranslate2",
    "tokenizers",
    "av",
    "onnxruntime",
    "numpy",
    "cv2",
    "yt_dlp",
    "resend",
    "psutil",
    "webview",
]

a = Analysis(
    [str(BACKEND / "clpz_server.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=[
        # faster-whisper VAD model — PyInstaller does not collect these assets
        (os.path.join(os.path.dirname(faster_whisper.__file__), "assets"), "faster_whisper/assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Nothing AWS may ship — hard-guarantee by exclusion
        "boto3", "botocore", "s3transfer",
        # Dev-only heavies not needed at runtime
        "tkinter", "matplotlib", "PIL.ImageQt", "pytest", "IPython",
        "jupyter", "pandas", "torch", "torchvision",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="clpz_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # keeps logs visible when run from a terminal for support
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="clpz_server",
)
