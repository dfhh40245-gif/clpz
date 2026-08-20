#!/usr/bin/env python3
"""ClipForge Desktop — development launcher.

Run this script to start the desktop application during development.

Usage:
    python run_desktop.py              # Normal start
    python run_desktop.py --debug      # Start with webview debug mode
    python run_desktop.py --port 9000  # Use a different port
"""
from __future__ import annotations

import argparse
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from desktop.app import run


def main():
    parser = argparse.ArgumentParser(description="Launch ClipForge Desktop")
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for the backend server (default: 8000)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable webview debug mode"
    )
    args = parser.parse_args()

    if args.debug:
        sys.argv = [sys.argv[0], "--debug"]

    run(port=args.port)


if __name__ == "__main__":
    main()
