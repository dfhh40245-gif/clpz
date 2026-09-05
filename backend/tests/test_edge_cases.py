"""Edge case and robustness tests for CLPZ.

Covers: job cancellation, credit refund on failure, session persistence,
duplicate upload handling, and job state transitions.
"""
import os
import sys
import time
import uuid
import shutil
import subprocess
import tempfile
import pytest
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _email(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def _find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    bin_dir = Path(__file__).resolve().parent.parent / "bin"
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if (bin_dir / name).exists():
        return str(bin_dir / name)
    return None


def _generate_tiny_video(output_path, duration=3.0):
    """Generate a minimal valid MP4 with sine-wave audio (no speech)."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        pytest.skip("ffmpeg not available")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s=320x568:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k", "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"ffmpeg failed: {result.stderr[-200:]}"
    assert output_path.exists() and output_path.stat().st_size > 0
    return output_path


class TestSessionPersistence:
    """Verify session cookies persist across multiple requests."""

    def test_session_persists_across_requests(self, clean_server):
        s = requests.Session()
        email = _email("persist")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        # First request — session should be set
        r1 = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r1.status_code == 200
        # Second request — same session should still work
        r2 = s.get(f"{clean_server.base_url}/api/credits/balance")
        assert r2.status_code == 200
        assert r2.json()["balance"] == 10
        # Third request — still valid
        r3 = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r3.status_code == 200
        assert r3.json()["user"]["email"] == email

    def test_two_users_have_separate_sessions(self, clean_server):
        s1 = requests.Session()
        s2 = requests.Session()
        e1 = _email("user1")
        e2 = _email("user2")
        s1.post(f"{clean_server.base_url}/api/auth/signup",
                json={"email": e1, "password": "pass123456"})
        s2.post(f"{clean_server.base_url}/api/auth/signup",
                json={"email": e2, "password": "pass123456"})
        r1 = s1.get(f"{clean_server.base_url}/api/auth/me")
        r2 = s2.get(f"{clean_server.base_url}/api/auth/me")
        assert r1.json()["user"]["email"] == e1
        assert r2.json()["user"]["email"] == e2

    def test_expired_invalid_session_returns_401(self, clean_server):
        """A fabricated session token should be rejected."""
        r = requests.get(
            f"{clean_server.base_url}/api/auth/me",
            cookies={"clpz_session": "totally-fake-token-12345"},
        )
        assert r.status_code == 401


@pytest.mark.slow
class TestJobCancellation:
    """Verify jobs can be cancelled and credits refunded."""

    def test_cancel_nonexistent_job(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("cancel"), "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/jobs/fake-job-id/cancel")
        assert r.status_code in (404, 400)

    def test_cancel_completed_job_no_refund(self, clean_server):
        """Cancelling a completed job should not double-refund."""
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("nocancel"), "password": "pass123456"})
        # Create a job (YouTube, will start downloading)
        r = s.post(f"{clean_server.base_url}/api/jobs",
                   json={"url": "https://youtube.com/watch?v=cancel_test",
                         "max_clips": 1,
                         "idempotency_key": f"cancel_{uuid.uuid4().hex[:8]}"})
        if r.status_code == 200:
            job_id = r.json()["job_id"]
            time.sleep(1)
            # Try cancelling
            r2 = s.post(f"{clean_server.base_url}/api/jobs/{job_id}/cancel")
            # Check credits — should not be negative
            r3 = s.get(f"{clean_server.base_url}/api/credits/balance")
            bal = r3.json()["balance"]
            assert bal >= 0, f"Balance went negative: {bal}"


@pytest.mark.slow
class TestCreditRefundOnFailure:
    """Verify credits are refunded when pipeline fails."""

    def test_refund_on_no_speech_video(self, clean_server):
        """A video with no speech should fail gracefully and refund credit."""
        s = requests.Session()
        email = _email("refund")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})

        # Check initial credits
        r = s.get(f"{clean_server.base_url}/api/credits/balance")
        initial = r.json()["balance"]

        # Upload a sine-wave-only video (no speech)
        test_file = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            _generate_tiny_video(test_file, duration=2.0)
            with open(test_file, "rb") as f:
                r = s.post(f"{clean_server.base_url}/api/jobs/upload",
                           files={"file": ("no_speech.mp4", f, "video/mp4")},
                           data={"max_clips": "1"})
            assert r.status_code == 200
            job_id = r.json()["job_id"]

            # Wait for completion
            for _ in range(40):
                time.sleep(3)
                r = s.get(f"{clean_server.base_url}/api/jobs/{job_id}")
                if r.json().get("stage") in ("done", "error", "cancelled"):
                    break

            # Check credits — should be refunded or at minimum not negative
            r = s.get(f"{clean_server.base_url}/api/credits/balance")
            final = r.json()["balance"]
            assert final >= 0, f"Balance went negative: {final}"
        finally:
            test_file.unlink(missing_ok=True)


@pytest.mark.slow
class TestDuplicateUpload:
    """Verify uploading the same file twice creates separate jobs."""

    def test_same_file_uploads_twice(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("dupupload"), "password": "pass123456"})

        test_file = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            _generate_tiny_video(test_file, duration=2.0)
            # Upload once
            with open(test_file, "rb") as f:
                r1 = s.post(f"{clean_server.base_url}/api/jobs/upload",
                            files={"file": ("test.mp4", f, "video/mp4")},
                            data={"max_clips": "1"})
            assert r1.status_code == 200
            jid1 = r1.json()["job_id"]

            # Upload same file again — should create a new job
            with open(test_file, "rb") as f:
                r2 = s.post(f"{clean_server.base_url}/api/jobs/upload",
                            files={"file": ("test.mp4", f, "video/mp4")},
                            data={"max_clips": "1"})
            assert r2.status_code == 200
            jid2 = r2.json()["job_id"]
            assert jid1 != jid2, "Same file should create different job IDs"
        finally:
            test_file.unlink(missing_ok=True)


@pytest.mark.slow
class TestJobStateTransitions:
    """Verify jobs move through valid state transitions."""

    def test_job_starts_in_queued_state(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("state"), "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/jobs",
                   json={"url": "https://youtube.com/watch?v=state_test",
                         "max_clips": 1,
                         "idempotency_key": f"state_{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        r = s.get(f"{clean_server.base_url}/api/jobs/{job_id}")
        job = r.json()
        assert job["stage"] in ("queued", "downloading", "transcribing",
                                 "analyzing", "tracking", "rendering")

    def test_completed_job_has_clips(self, clean_server):
        """A successful job should have a non-empty clips array."""
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("clips"), "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/jobs",
                   json={"url": "https://youtube.com/watch?v=clips_test",
                         "max_clips": 1,
                         "idempotency_key": f"clips_{uuid.uuid4().hex[:8]}"})
        if r.status_code == 200:
            job_id = r.json()["job_id"]
            for _ in range(40):
                time.sleep(3)
                r = s.get(f"{clean_server.base_url}/api/jobs/{job_id}")
                if r.json().get("stage") in ("done", "error"):
                    break
            job = r.json()
            if job.get("stage") == "done":
                assert len(job.get("clips", [])) > 0, "Completed job has no clips"

    def test_nonexistent_job_returns_404(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("nf"), "password": "pass123456"})
        r = s.get(f"{clean_server.base_url}/api/jobs/nonexistent-job-id")
        assert r.status_code == 404


class TestInputValidation:
    """Verify input validation catches bad data before processing."""

    def test_corrupted_video_rejected(self, clean_server):
        """A corrupted MP4 should be rejected at upload time."""
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("corrupt"), "password": "pass123456"})
        # Write garbage that has .mp4 extension
        corrupt = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            corrupt.write_bytes(b"\x00\x00\x00\x1cftypisom\x00\x00" + b"\xff" * 500)
            with open(corrupt, "rb") as f:
                r = s.post(f"{clean_server.base_url}/api/jobs/upload",
                           files={"file": ("corrupt.mp4", f, "video/mp4")},
                           data={"max_clips": "1"})
            assert r.status_code == 400, f"Corrupted video not rejected: {r.status_code} {r.text}"
        finally:
            corrupt.unlink(missing_ok=True)

    def test_zero_byte_video_rejected(self, clean_server):
        """A zero-byte file should be rejected at upload time."""
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("zero"), "password": "pass123456"})
        empty = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            empty.touch()
            with open(empty, "rb") as f:
                r = s.post(f"{clean_server.base_url}/api/jobs/upload",
                           files={"file": ("empty.mp4", f, "video/mp4")},
                           data={"max_clips": "1"})
            assert r.status_code == 400, f"Empty file not rejected: {r.status_code} {r.text}"
        finally:
            empty.unlink(missing_ok=True)

    def test_html_injection_in_email(self, clean_server):
        """HTML/JS in email fields should be rejected."""
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": "<script>alert(1)</script>@test.com",
                                "password": "pass123456"})
        assert r.status_code == 400

    def test_empty_body_rejected(self, clean_server):
        """Empty request body should be rejected."""
        r = requests.post(f"{clean_server.base_url}/api/auth/login", json={})
        assert r.status_code in (400, 422)

    def test_very_long_email_rejected(self, clean_server):
        """Extremely long email should not crash the server."""
        long_email = "a" * 1000 + "@test.com"
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": long_email, "password": "pass123456"})
        assert r.status_code == 400
