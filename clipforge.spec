# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ClipForge Desktop.

Build with:
    pyinstaller clipforge.spec

This produces a dist/ClipForge/ directory with the executable.
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all backend Python files
backend_path = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'backend')

a = Analysis(
    ['run_desktop.py'],
    pathex=[
        os.path.dirname(os.path.abspath(SPEC)),
        backend_path,
    ],
    binaries=[],  # FFmpeg binaries included via datas in backend/bin/
    datas=[
        # Frontend HTML — all pages the backend serves
        ('frontend/index.html', 'frontend'),
        ('frontend/clpz.html', 'frontend'),
        ('frontend/auth.html', 'frontend'),
        ('frontend/admin.html', 'frontend'),
        ('frontend/config.js', 'frontend'),
        # Backend Python modules (imported at runtime)
        (backend_path, 'backend'),
    ],
    hiddenimports=[
        # FastAPI and uvicorn
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.responses',
        'pydantic',
        'starlette',
        'starlette.responses',
        'starlette.routing',
        # HTTP/file upload support
        'requests',
        'multipart',
        'python_multipart',
        # Backend modules
        'config',
        'database',
        'jobs',
        'credits',
        'auth',
        'email_service',
        'pipeline.analyzer',
        'pipeline.captions',
        'pipeline.cutter',
        'pipeline.downloader',
        'pipeline.srt_parser',
        'pipeline.transcriber',
        # Transcription dependencies
        'faster_whisper',
        'ctranslate2',
        'onnxruntime',
        'tokenizers',
        # Desktop modules
        'desktop',
        'desktop.app',
        'desktop.server',
        # Webview
        'webview',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClipForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ClipForge',
)
