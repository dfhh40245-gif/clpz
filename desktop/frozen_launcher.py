"""CLPZ Desktop — frozen-application launcher (packaged build).

Starts the packaged backend (clpz_server.exe) as a child process, waits for
it to answer, then opens the PyWebView window. All paths resolve relative to
the installation directory; nothing is hard-coded.

Development still uses run_desktop.py; this launcher is for the frozen app.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _free_port(preferred: int) -> int:
    """Return preferred if free, else an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 60.0) -> bool:
    import urllib.request

    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/diagnostics"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def _data_dir(base: Path) -> Path:
    """User-data dir — never inside Program Files (not writable without admin).

    Order: CLIPFORGE_DATA env > %LOCALAPPDATA%/CLPZ/data > base/data.
    Must stay in sync with backend/clpz_server.py::_data_dir.
    """
    env = os.environ.get("CLIPFORGE_DATA")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        p = Path(local_app) / "CLPZ" / "data"
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.touch(); probe.unlink()
            return p
        except OSError:
            pass
    p = base / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> None:
    import webview

    base = _base_dir()
    port = _free_port(8765)

    server_exe = base / "clpz_server.exe"
    data_dir = _data_dir(base)

    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = str(data_dir)
    env.setdefault("CLPZ_DEBUG", "0")

    if server_exe.exists():
        cmd = [str(server_exe), "serve", "--port", str(port)]
    else:
        # Dev fallback: run via python (unfrozen debugging of this launcher)
        cmd = [sys.executable, str(base / "backend" / "clpz_server.py"),
               "serve", "--port", str(port)]

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd, cwd=str(base), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        if not _wait_ready(port):
            raise RuntimeError(
                "CLPZ backend failed to start. "
                f"Check logs in {data_dir / 'clpz_server.log'}"
            )

        window = webview.create_window(
            title="CLPZ",
            # Desktop workspace: local processing, no login required
            # (same flow as the dev CLPZ.bat launcher).
            url=f"http://127.0.0.1:{port}/app?desktop=1",
            width=1280,
            height=840,
            min_size=(900, 620),
            text_select=True,
        )

        def on_closed():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        window.events.closed += on_closed
        webview.start(debug=("--debug" in sys.argv))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
