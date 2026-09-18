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
    """Wait for OUR backend to become ready (task 12).

    Readiness = the child process answering /api/diagnostics with JSON
    containing our app marker — an unrelated listener that happens to own
    the port will not answer with the expected payload and cannot masquerade
    as readiness.
    """
    import json
    import urllib.request

    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/diagnostics"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    try:
                        payload = json.loads(r.read().decode("utf-8", "replace"))
                        if isinstance(payload, dict) and payload.get("platform"):
                            return True  # JSON diagnostics = our backend shape
                    except (ValueError, UnicodeDecodeError):
                        pass  # some other server answered; keep waiting
        except Exception:
            pass
        time.sleep(0.4)
    return False


def _stop_process(proc) -> None:
    """Terminate a child and its tree; escalate to kill. Never raises."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


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


def _spawn_server(base, port, env):
    """Spawn the packaged server. Package-layout contract (task 12): the
    installed build places the server at clpz_server/clpz_server.exe under
    the install root. The dev fallback runs the backend entry from source; a
    frozen launcher never falls back to running itself as a Python
    interpreter. Startup errors go to user-accessible launcher.log.
    """
    candidates = [
        base / "clpz_server" / "clpz_server.exe",  # installed assembly layout
        base / "clpz_server.exe",                    # flat layout (older builds)
    ]
    server_exe = next((p for p in candidates if p.exists()), None)
    if server_exe is not None:
        cmd = [str(server_exe), "serve", "--port", str(port)]
    elif not getattr(sys, "frozen", False):
        # Dev fallback: run via python (unfrozen debugging of this launcher)
        cmd = [sys.executable, str(base / "backend" / "clpz_server.py"),
               "serve", "--port", str(port)]
    else:
        raise RuntimeError(
            f"CLPZ server executable not found (looked for "
            f"{candidates[0]} and {candidates[1]}). The installation appears "
            "to be incomplete — reinstall CLPZ."
        )
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Route child output into a user-accessible log next to the data dir so
    # startup failures are diagnosable (task 12); the server additionally
    # logs to data/logs/clpz_server.log itself.
    log_path = Path(env.get("CLIPFORGE_DATA", str(base))) / "launcher.log"
    log_file = open(log_path, "ab", buffering=0)
    try:
        log_file.write(f"[launcher] starting {cmd}\n".encode("utf-8"))
    except Exception:
        pass
    return subprocess.Popen(
        cmd, cwd=str(base), env=env,
        stdout=log_file, stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )


def _run_watchdog(current, window, base, port, env, closing):
    """Detect unexpected backend death and restart it (single replacement,
    no duplicate servers).

    Task 12 ownership contract: the replacement handle replaces the original
    in the shared holder, so a window close tears down the REPLACEMENT (the
    previously running child died — there is nothing else to stop). The
    holder is shared with the closer thread via the ``closing``/holder
    pattern in ``main``.
    """
    import time as _time

    holder = current
    while not closing.is_set():
        proc = holder[0]
        if proc.poll() is not None:
            # Unexpected crash — attempt exactly one restart, then reload the UI.
            new_proc = _spawn_server(base, port, env)
            if _wait_ready(port):
                holder[0] = new_proc  # ownership transfers to the holder
                window.load_url(f"http://127.0.0.1:{port}/app?desktop=1")
                return  # do not respawn again (single replacement policy)
            _stop_process(new_proc)
            return
        _time.sleep(2)


def main() -> None:
    import threading
    import webview

    base = _base_dir()
    port = _free_port(8765)
    data_dir = _data_dir(base)

    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = str(data_dir)
    # Frozen app: FORCE production security settings. A developer can opt in
    # to debug explicitly with --clpz-debug; inherited CLPZ_DEBUG=1 from the
    # shell must never expose development endpoints in the installed app.
    env["CLPZ_DEBUG"] = "0"
    env.pop("CLPZ_REQUIRE_CAPABILITY", None)  # always keep the gate on
    if "--clpz-debug" in sys.argv:
        env["CLPZ_DEBUG"] = "1"

    # Per-launch capability (task 03): rotate a fresh token for this launch
    # and hand it ONLY to this launch's server process. The UI receives it via
    # the /app page injection, never via URL or logs.
    import secrets
    capability_token = secrets.token_urlsafe(32)
    env["CLPZ_CAPABILITY_TOKEN"] = capability_token

    proc = _spawn_server(base, port, env)
    # Shared holder: the watchdog transfers replacement ownership here and
    # close/finally tears down whatever handle is current (task 12).
    proc_holder = [proc]

    try:
        if not _wait_ready(port):
            raise RuntimeError(
                "CLPZ backend failed to start. "
                f"Check {data_dir / 'launcher.log'} and "
                f"{data_dir / 'logs' / 'clpz_server.log'}"
            )

        window = webview.create_window(
            title="CLPZ",
            # Desktop workspace: local processing, no login required
            # (same flow as the dev CLPZ.bat launcher). The capability token
            # travels inside the served /app page, never in this URL.
            url=f"http://127.0.0.1:{port}/app?desktop=1",
            width=1280,
            height=840,
            min_size=(900, 620),
            text_select=True,
        )

        closing = threading.Event()

        def on_closed():
            closing.set()
            # Tear down whichever child handle is CURRENT (the watchdog may
            # have replaced the original after a crash — task 12).
            _stop_process(proc_holder[0])

        window.events.closed += on_closed
        # Watchdog: restart the backend if it crashes while the app is open.
        threading.Thread(
            target=_run_watchdog,
            args=(proc_holder, window, base, port, env, closing),
            daemon=True,
            name="clpz-watchdog",
        ).start()
        webview.start(debug=("--debug" in sys.argv))
    finally:
        closing.set()
        _stop_process(proc_holder[0])


if __name__ == "__main__":
    main()
