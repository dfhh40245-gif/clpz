"""Cross-module subprocess registry.

jobs.py and the pipeline modules both import this, so a job can terminate the
child FFmpeg / yt-dlp processes it launched even though the pipeline code
lives in separate modules (which cannot import jobs.py without a cycle).

Every subprocess spawned on behalf of a job is registered here and torn down
on cancellation, timeout, or application shutdown.  On Windows, process trees
are terminated with ``taskkill /T /F`` so grandchildren (ffmpeg's own workers)
are not orphaned.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from types import SimpleNamespace

_active: dict[str, set[subprocess.Popen]] = {}
_lock = threading.Lock()


def _kill_proc(p: subprocess.Popen) -> None:
    """Force-kill a process and (on Windows) its whole tree."""
    if p.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                capture_output=True, timeout=10,
            )
            return
        except Exception:
            pass
    try:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def register(job_id: str, p: subprocess.Popen) -> None:
    with _lock:
        _active.setdefault(job_id, set()).add(p)


def unregister(job_id: str, p: subprocess.Popen) -> None:
    with _lock:
        s = _active.get(job_id)
        if s:
            s.discard(p)
            if not s:
                _active.pop(job_id, None)


def kill_job(job_id: str) -> int:
    """Terminate every live subprocess registered to a job. Returns count killed."""
    with _lock:
        procs = list(_active.get(job_id, ()))
    n = 0
    for p in procs:
        if p.poll() is None:
            _kill_proc(p)
            n += 1
    return n


def kill_all() -> None:
    with _lock:
        ids = list(_active.keys())
    for jid in ids:
        kill_job(jid)


def active_count() -> int:
    with _lock:
        return sum(len(v) for v in _active.values())


def prune(job_id: str) -> None:
    """Drop finished processes from the registry (defensive)."""
    with _lock:
        s = _active.get(job_id)
        if s:
            dead = [p for p in s if p.poll() is not None]
            for p in dead:
                s.discard(p)
            if not s:
                _active.pop(job_id, None)


def run(job_id: str, cmd: list[str], timeout: float | None = None,
        capture_output: bool = True, check: bool = False, text: bool = True,
        **kw) -> SimpleNamespace:
    """subprocess.run replacement that registers the child against a job.

    Returns a SimpleNamespace exposing ``returncode``/``stdout``/``stderr``
    (matching ``subprocess.CompletedProcess``).  Raises ``TimeoutExpired`` on
    timeout (after force-killing the tree).  When ``check`` is set, raises
    ``CalledProcessError`` on a non-zero exit (mirroring ``subprocess.run``).
    """
    if capture_output:
        kw.setdefault("stdout", subprocess.PIPE)
        kw.setdefault("stderr", subprocess.PIPE)
    kw.setdefault("text", text)
    p = subprocess.Popen(cmd, **kw)
    register(job_id, p)
    try:
        out, err = p.communicate(timeout=timeout)
        res = SimpleNamespace(returncode=p.returncode, stdout=out, stderr=err)
    except subprocess.TimeoutExpired:
        _kill_proc(p)
        raise
    finally:
        unregister(job_id, p)
    if check and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, output=out, stderr=err)
    return res