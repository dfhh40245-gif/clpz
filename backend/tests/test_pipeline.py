"""Pipeline unit tests and failure case tests for CLPZ."""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import pytest
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSRTParser:
    def test_parse_simple_srt(self):
        from pipeline.srt_parser import parse_srt
        srt_content = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n2\n00:00:03,500 --> 00:00:05,000\nThis is a test\n"
        srt_file = Path(tempfile.mktemp(suffix=".srt"))
        srt_file.write_text(srt_content, encoding="utf-8")
        try:
            result = parse_srt(srt_file)
            assert isinstance(result, dict)
            assert "segments" in result or "words" in result
        finally:
            srt_file.unlink(missing_ok=True)

    def test_parse_empty_srt_raises(self):
        from pipeline.srt_parser import parse_srt
        srt_file = Path(tempfile.mktemp(suffix=".srt"))
        srt_file.write_text("", encoding="utf-8")
        try:
            with pytest.raises(ValueError):
                parse_srt(srt_file)
        finally:
            srt_file.unlink(missing_ok=True)


class TestVideoValidation:
    def test_validate_real_video(self):
        from jobs import _validate_output
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            bin_dir = Path(__file__).resolve().parent.parent / "bin"
            name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            if (bin_dir / name).exists(): ffmpeg = str(bin_dir / name)
            else: pytest.skip("ffmpeg not available")
        test_file = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=1",
                           "-f", "lavfi", "-i", "sine=frequency=300:duration=1",
                           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                           "-c:a", "aac", "-shortest", str(test_file)],
                          capture_output=True, timeout=10)
            result = _validate_output(test_file)
            assert result["valid"], f"Validation failed: {result.get('error')}"
        finally:
            test_file.unlink(missing_ok=True)

    def test_validate_nonexistent_file(self):
        from jobs import _validate_output
        result = _validate_output(Path("/nonexistent/file.mp4"))
        assert not result["valid"]

    def test_validate_empty_file(self):
        from jobs import _validate_output
        test_file = Path(tempfile.mktemp(suffix=".mp4"))
        test_file.touch()
        try:
            result = _validate_output(test_file)
            assert not result["valid"]
        finally:
            test_file.unlink(missing_ok=True)


class TestDatabaseOperations:
    def test_user_crud(self):
        import database as db
        import hashlib
        pwd_hash = hashlib.pbkdf2_hmac("sha256", b"test", b"salt", 100000).hex()
        db.create_user("dbtest1", "dbtest@test.com", pwd_hash, "salt", "DB Test")
        user = db.get_user_by_email("dbtest@test.com")
        assert user is not None
        assert user["email"] == "dbtest@test.com"
        user2 = db.get_user_by_id(user["id"])
        assert user2 is not None
        conn = db._get_conn()
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        conn.commit()
        assert db.get_user_by_id(user["id"]) is None

    def test_credit_operations(self):
        import database as db
        import hashlib
        pwd_hash = hashlib.pbkdf2_hmac("sha256", b"test", b"salt", 100000).hex()
        db.create_user("credtest1", "cred@test.com", pwd_hash, "salt")
        user = db.get_user_by_email("cred@test.com")
        uid = user["id"]
        try:
            assert db.get_credit_balance(uid) == 0
            db.set_credit_balance(uid, 10)
            assert db.get_credit_balance(uid) == 10
            ok, remaining = db.check_and_charge(uid, 3)
            assert ok and remaining == 7
            ok, remaining = db.check_and_charge(uid, 100)
            assert not ok and remaining == 7
            new_bal = db.refund_credits(uid, 2, reason="test")
            assert new_bal == 9
        finally:
            conn = db._get_conn()
            conn.execute("DELETE FROM credit_transactions WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM credits WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            conn.commit()


class TestFailureCases:
    def test_invalid_video_format(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": "format@test.com", "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/jobs/upload",
                   files={"file": ("test.exe", b"MZ\x90\x00", "application/octet-stream")})
        assert r.status_code == 400

    def test_unauthorized_credit_access(self, clean_server):
        r = requests.get(f"{clean_server.base_url}/api/credits/balance")
        assert r.status_code == 401
