#!/usr/bin/env python3
"""ClipForge Desktop — build script for Windows .exe packaging.

Run this to create a distributable Windows application.

Usage:
    python build_exe.py

Output:
    dist/ClipForge/ClipForge.exe
"""
from __future__ import annotations

import os
import subprocess
import sys
import shutil


def main():
    print("=" * 60)
    print("  ClipForge Desktop — Building Windows .exe")
    print("=" * 60)
    print()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(project_dir, "clipforge.spec")

    if not os.path.exists(spec_file):
        print(f"ERROR: Spec file not found: {spec_file}")
        sys.exit(1)

    # Clean previous builds
    dist_dir = os.path.join(project_dir, "dist")
    build_dir = os.path.join(project_dir, "build")

    for d in [dist_dir, build_dir]:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            shutil.rmtree(d)

    # Run PyInstaller
    print()
    print("Running PyInstaller...")
    print()

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        spec_file,
    ]

    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode != 0:
        print()
        print("BUILD FAILED")
        sys.exit(1)

    # Check output
    exe_path = os.path.join(dist_dir, "ClipForge", "ClipForge.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print()
        print("=" * 60)
        print("  BUILD SUCCESSFUL")
        print("=" * 60)
        print()
        print(f"  Output: {exe_path}")
        print(f"  Size:   {size_mb:.1f} MB")
        print()
        print("  To distribute:")
        print("    1. Copy the entire dist/ClipForge/ folder")
        print("    2. Users double-click ClipForge.exe to run")
        print()
        print("  Requirements for end users:")
        print("    - Windows 10/11")
        print("    - WebView2 runtime (usually pre-installed on Windows 10+)")
        print("    - FFmpeg in PATH or bundled in the dist folder")
        print()
    else:
        print()
        print("BUILD FAILED — exe not found at expected path")
        sys.exit(1)


if __name__ == "__main__":
    main()
