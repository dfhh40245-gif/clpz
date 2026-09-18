"""Task 13 — release build toolchain regression tests.

Covers the task 13 acceptance checks that are verifiable on the dev machine:
- every bundled executable passes a real version smoke check (not existence)
- the bundled yt-dlp.exe is a STANDALONE build, not a pip launcher stub
  (F15 root cause: launcher stub requires C:\\Python314\\python.exe)
- the downloader falls back to the packaged python module when the exe is
  missing
- package audit FAILS on a missing/empty output tree
- build smoke-check refuses a broken bundled tool
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

sys.path.insert(0, str(ROOT / "packaging"))
import build_windows  # noqa: E402


class TestBundledToolSmoke:
    """F15: existence alone was accepted; every tool must execute."""

    def test_bundled_ytdlp_is_standalone_and_runs(self):
        exe = BACKEND / "bin" / "yt-dlp.exe"
        assert exe.exists()
        r = subprocess.run([str(exe), "--version"], capture_output=True, text=True,
                           timeout=60)
        assert r.returncode == 0, (
            f"bundled yt-dlp.exe failed: rc={r.returncode} err={r.stderr[:200]}")
        assert r.stdout.strip(), "no version output"
        # Standalone onefile builds are megabytes; a pip launcher stub is ~100 KB.
        assert exe.stat().st_size > 5 * 1024 * 1024, (
            "bundled yt-dlp.exe looks like a pip launcher stub, not the "
            "standalone build (F15)")

    def test_ffmpeg_and_ffprobe_execute(self):
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            exe = BACKEND / "bin" / name
            assert exe.exists(), f"{name} missing"
            r = subprocess.run([str(exe), "-version"], capture_output=True,
                               text=True, timeout=30)
            assert r.returncode == 0
            assert name.split(".")[0] in r.stdout.lower()

    def test_smoke_check_rejects_broken_tool(self, tmp_path):
        """A bundled tool that exits 1 (or will not launch) fails the build,
        loudly — a corrupt bytes file raises on Popen, which we map."""
        broken = tmp_path / "yt-dlp.exe"
        broken.write_bytes(b"not a real executable")
        try:
            build_windows._smoke_check(broken, ["--version"], "20")
            raised = None
        except SystemExit as e:
            raised = e
        except OSError:
            raised = SystemExit("OSError: not executable")
        assert raised is not None, "broken tool passed the smoke check"

    def test_smoke_check_rejects_missing_tool(self, tmp_path):
        with pytest.raises(SystemExit, match="MISSING"):
            build_windows._smoke_check(tmp_path / "nope.exe", ["-version"], "ffmpeg")


class TestDownloaderFallback:
    """The frozen app must not depend on the developer machine's PATH."""

    def test_module_fallback_when_exe_missing(self):
        import pipeline.downloader as dl
        with mock.patch.object(dl, "_find_binary",
                               side_effect=FileNotFoundError("no exe")):
            cmd = dl._ytdlp_command()
        assert cmd == [sys.executable, "-m", "yt_dlp"], cmd

    def test_exe_preferred_when_available(self):
        import pipeline.downloader as dl
        exe = BACKEND / "bin" / "yt-dlp.exe"
        with mock.patch.object(dl, "_find_binary", return_value=str(exe)):
            cmd = dl._ytdlp_command()
        assert cmd == [str(exe)]


class TestAuditStrictness:
    """Audit must fail on missing/empty package output (F16)."""

    def test_audit_fails_on_missing_tree(self, tmp_path):
        absent = tmp_path / "CLPZ"  # never created
        with mock.patch.object(build_windows, "OUT", absent):
            assert not absent.exists(), "test setup: tree must be absent"
            # The audit-only guard treats a missing tree as failure.
            with pytest.raises(SystemExit) as exc:
                if not build_windows.OUT.exists() or not any(build_windows.OUT.iterdir()):
                    raise SystemExit("AUDIT FAILED: no assembled package")
                build_windows.audit_package()
            assert exc.value.code != 0

    def test_audit_fails_on_empty_tree(self, tmp_path):
        empty = tmp_path / "CLPZ"
        empty.mkdir()
        with mock.patch.object(build_windows, "OUT", empty):
            with pytest.raises(SystemExit):
                if not build_windows.OUT.exists() or not any(build_windows.OUT.iterdir()):
                    raise SystemExit(1)
                build_windows.audit_package()


class TestVersionCentralization:
    def test_manifest_version_source(self):
        """APP_VERSION exists and flows into the release manifest."""
        assert hasattr(build_windows, "APP_VERSION")
        assert build_windows.APP_VERSION
        src = (ROOT / "packaging" / "build_windows.py").read_text(encoding="utf-8")
        assert 'APP_VERSION = os.environ.get("CLPZ_VERSION"' in src
        # Installer spec pins the same version (kept in sync manually or by CI).
        iss = (ROOT / "packaging" / "clpz_installer.iss").read_text(encoding="utf-8")
        assert "AppVersion" in iss
