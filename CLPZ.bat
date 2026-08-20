@echo off
REM ClipForge Desktop — double-click to launch
REM This runs the desktop app in development mode.
REM For the packaged version, use ClipForge.exe instead.

cd /d "%~dp0"
python run_desktop.py %*
