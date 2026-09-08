"""Backend server manager — starts/stops the FastAPI app as a subprocess."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def _find_python() -> str:
    """Find the Python executable to use for the backend.

    Priority:
    1. Backend venv python (if it has Scripts/python.exe on Windows)
    2. System python (the same interpreter running this code)
    """
    # Check if backend venv has a working Windows python
    venv_python = Path(__file__).resolve().parent.parent / "backend" / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)

    # Fall back to current interpreter
    return sys.executable


def _find_ffmpeg_dir() -> Path | None:
    """Find a bundled FFmpeg directory, or None if not bundled."""
    project_root = Path(__file__).resolve().parent.parent

    # Check for bundled FFmpeg in backend/bin/ (development layout)
    dev_bin = project_root / "backend" / "bin"
    if (dev_bin / "ffmpeg.exe").exists() or (dev_bin / "ffmpeg").exists():
        return dev_bin

    # When packaged as exe, check next to the exe
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for subdir in ["ffmpeg", "bin", "backend/bin", ""]:
            check_dir = exe_dir / subdir if subdir else exe_dir
            if (check_dir / "ffmpeg.exe").exists() or (check_dir / "ffmpeg").exists():
                return check_dir

    return None


def _is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll localhost until the backend responds or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False


class BackendServer:
    """Manages the FastAPI backend as a subprocess."""

    def __init__(self, port: int = 8000):
        self.port = port
        self.process: subprocess.Popen | None = None
        self._backend_dir = Path(__file__).resolve().parent.parent / "backend"
        self._stdout_f = None
        self._stderr_f = None

    def _data_dir(self) -> Path:
        """Desktop data dir: per-user app data, isolated from backend defaults."""
        if getattr(sys, "frozen", False):
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "CLPZ"
        # Dev layout: project-root/desktop_data so tests never touch backend/data.
        return Path(__file__).resolve().parent.parent / "desktop_data"

    def start(self) -> None:
        """Start the backend server."""
        if not _is_port_available(self.port):
            raise RuntimeError(
                f"Port {self.port} is already in use. "
                "Close the other application or set CLIPFORGE_PORT."
            )

        python_exe = _find_python()

        # Build environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self._backend_dir)
        # Desktop mode is a local, single-user product: production security
        # settings, isolated data dir (never the backend's default ./data).
        env.setdefault("CLPZ_DEBUG", "0")
        data_dir = self._data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        env["CLIPFORGE_DATA"] = str(data_dir)

        # Add bundled FFmpeg to PATH if available
        ffmpeg_dir = _find_ffmpeg_dir()
        if ffmpeg_dir:
            env["PATH"] = str(ffmpeg_dir) + os.pathsep + env.get("PATH", "")

        # Start uvicorn pointing at the backend's main.py
        cmd = [
            python_exe,
            "-m", "uvicorn",
            "main:app",
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--log-level", "warning",
        ]

        # Redirect server output to log files instead of PIPEs.  Never-drained
        # pipes fill their 64KB buffer once the server logs enough (e.g. long
        # tracebacks) and permanently deadlock the backend mid-session.
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_f = open(log_dir / "clpz_server.log", "ab")
        self._stderr_f = open(log_dir / "clpz_server.err.log", "ab")

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self._backend_dir),
            env=env,
            stdout=self._stdout_f,
            stderr=self._stderr_f,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0
            ),
        )

        # Wait for the server to be ready
        if not _wait_for_server(self.port, timeout=30):
            stderr = ""
            try:
                self._stderr_f.flush()
                stderr = (log_dir / "clpz_server.err.log").read_text(
                    encoding="utf-8", errors="replace")[-2000:]
            except OSError:
                pass
            self.stop()
            raise RuntimeError(
                f"Backend failed to start within 30 seconds.\n{stderr}"
            )

    def stop(self) -> None:
        """Stop the backend server gracefully."""
        if self.process is None:
            return

        if self.process.poll() is None:
            # Try graceful shutdown first
            if sys.platform == "win32":
                self.process.terminate()
            else:
                self.process.send_signal(signal.SIGTERM)

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

        self.process = None
        for f in (self._stdout_f, self._stderr_f):
            if f:
                try:
                    f.close()
                except OSError:
                    pass
        self._stdout_f = None
        self._stderr_f = None

    def url(self) -> str:
        """Return the backend URL."""
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
