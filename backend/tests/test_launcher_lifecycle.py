"""Task 12 — installed Windows startup and shutdown regression tests.

Covers the task 12 acceptance checks:
- a staged install layout selects clpz_server/clpz_server.exe exactly; a
  missing server exe fails clearly in frozen mode (never runs itself)
- watchdog replacement ownership: the replacement handle is stored in the
  shared holder so close tears down the CURRENT child, not the dead one
- inherited CLPZ_DEBUG=1 cannot survive into the frozen app's environment
- readiness requires our app's JSON diagnostics, not just any listener
"""
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from desktop import frozen_launcher  # noqa: E402


# ── Package-layout contract ─────────────────────────────────────────────


def test_staged_layout_chooses_packaged_server(tmp_path):
    """Assembly layout: clpz_server/clpz_server.exe must be the child."""
    base = tmp_path / "install"
    (base / "clpz_server").mkdir(parents=True)
    exe = base / "clpz_server" / "clpz_server.exe"
    exe.write_bytes(b"MZ")
    (base / "data").mkdir()

    captured = {}

    class FakeProc:
        def __init__(self):
            self.pid = 4242
            self.poll = lambda: 0

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    with mock.patch.object(frozen_launcher.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(frozen_launcher, "open", mock.mock_open(), create=True):
        frozen_launcher._spawn_server(base, 8765, {"CLIPFORGE_DATA": str(tmp_path)})
    assert captured["cmd"][0] == str(exe), captured["cmd"]
    assert "serve" in captured["cmd"] and "--port" in captured["cmd"]


def test_frozen_missing_server_fails_clearly(tmp_path):
    """A frozen launcher without the server exe raises a clear install error
    instead of silently running python from the install root."""
    base = tmp_path / "broken-install"
    base.mkdir()
    with mock.patch.object(frozen_launcher.sys, "frozen", True, create=True):
        with pytest.raises(RuntimeError, match="not found|reinstall"):
            frozen_launcher._spawn_server(base, 8765, {"CLIPFORGE_DATA": str(tmp_path)})


def test_dev_layout_falls_back_to_source_entry(tmp_path):
    """Unfrozen dev launcher still works from source (backend/clpz_server.py)."""
    base = tmp_path
    (base / "backend").mkdir(exist_ok=True)
    (base / "backend" / "clpz_server.py").write_text("# entry", encoding="utf-8")

    captured = {}

    class FakeProc:
        pid = 1
        def poll(self):
            return 0

    with mock.patch.object(frozen_launcher.subprocess, "Popen",
                           return_value=FakeProc()) as popen, \
         mock.patch.object(frozen_launcher, "open", mock.mock_open(), create=True):
        frozen_launcher._spawn_server(base, 8765, {"CLIPFORGE_DATA": str(tmp_path)})
        cmd = popen.call_args.args[0]
    assert cmd[0] == sys.executable
    assert cmd[1].endswith("clpz_server.py")


# ── Watchdog replacement ownership ──────────────────────────────────────


def test_watchdog_transfers_replacement_ownership(tmp_path):
    """After a crash + successful replacement, the holder holds the NEW proc
    (close will tear down the replacement, not the dead original)."""
    dead = SimpleNamespace(pid=1, poll=lambda: 1)          # original crashed
    replacement = SimpleNamespace(pid=2, poll=lambda: None)  # new child

    base = tmp_path
    closing = threading.Event()  # NOT set: the single-replacement policy
    # returns after one attempt, so the loop must be allowed to run once.

    window = mock.Mock()
    with mock.patch.object(frozen_launcher, "_spawn_server",
                           return_value=replacement) as spawn, \
         mock.patch.object(frozen_launcher, "_wait_ready", return_value=True):
        holder = [dead]
        frozen_launcher._run_watchdog(holder, window, base, 8765, {}, closing)

    assert spawn.called, "watchdog did not attempt a replacement"
    assert holder[0] is replacement, (
        "replacement ownership was not transferred to the close path")
    assert window.load_url.called


def test_watchdog_kills_failed_replacement(tmp_path):
    """If the replacement never becomes ready it is stopped, and the holder
    keeps the (dead) original — nothing new leaks."""
    dead = SimpleNamespace(pid=1, poll=lambda: 1)
    replacement = SimpleNamespace(pid=2, poll=lambda: None,
                                  kill=mock.Mock(), terminate=mock.Mock(),
                                  wait=mock.Mock())

    base = tmp_path
    closing = threading.Event()
    window = mock.Mock()
    with mock.patch.object(frozen_launcher, "_spawn_server", return_value=replacement), \
         mock.patch.object(frozen_launcher, "_wait_ready", return_value=False):
        holder = [dead]
        frozen_launcher._run_watchdog(holder, window, base, 8765, {}, closing)

    assert not window.load_url.called
    assert replacement.terminate.called or replacement.kill.called
    assert holder[0] is dead


# ── Production security in frozen mode ──────────────────────────────────


def test_debug_env_doc_contract():
    """The launcher forces CLPZ_DEBUG=0 before spawning, and --clpz-debug is
    the only explicit opt-in back. Static contract check (the real spawn is
    exercised by the clean-machine acceptance run)."""
    src = (ROOT / "desktop" / "frozen_launcher.py").read_text(encoding="utf-8")
    assert 'env["CLPZ_DEBUG"] = "0"' in src
    assert "--clpz-debug" in src
    assert 'env.pop("CLPZ_REQUIRE_CAPABILITY", None)' in src


# ── Readiness: an unrelated listener cannot masquerade ──────────────────


def test_readiness_rejects_foreign_server(tmp_path, monkeypatch):
    """A port owned by a non-CLPZ HTTP server must not count as ready."""
    import http.server
    import threading as th

    class Foreign(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"<html>totally unrelated service</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Foreign)
    port = srv.server_address[1]
    t = th.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        # Short timeout: a foreign 200 must not satisfy readiness.
        assert frozen_launcher._wait_ready(port, timeout=1.5) is False
    finally:
        srv.shutdown()
        srv.server_close()


def test_readiness_accepts_clpz_diagnostics_shape(monkeypatch):
    """JSON diagnostics with a platform field satisfies readiness."""
    import io
    import json as _json

    payload = {"platform": "Windows", "python": "3.12"}

    class FakeResp(io.BytesIO):
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, n=-1):
            return _json.dumps(payload).encode()

    with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
        assert frozen_launcher._wait_ready(8765, timeout=1.0) is True


# ── Close tears down the current child ──────────────────────────────────


def test_stop_process_is_safe_and_escalates():
    alive = SimpleNamespace(pid=3, poll=lambda: None,
                            terminate=mock.Mock(),
                            wait=mock.Mock(return_value=0),
                            kill=mock.Mock())
    frozen_launcher._stop_process(alive)
    assert alive.terminate.called

    # A terminate that times out escalates to kill.
    stubborn = SimpleNamespace(
        pid=4, poll=lambda: None, terminate=mock.Mock(),
        wait=mock.Mock(side_effect=subprocess.TimeoutExpired("x", 5)),
        kill=mock.Mock())
    frozen_launcher._stop_process(stubborn)
    assert stubborn.kill.called

    # Already-dead / None handles are no-ops (never raise).
    frozen_launcher._stop_process(None)
    frozen_launcher._stop_process(SimpleNamespace(pid=5, poll=lambda: 0,
                                                  terminate=mock.Mock()))
