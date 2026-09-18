"""R06 — support-bundle privacy contract tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import support_bundle as bundle  # noqa: E402


@pytest.mark.parametrize("text, private_values", [
    (
        '{"password": "synthetic-json-password", "token": "synthetic-json-token"}',
        ("synthetic-json-password", "synthetic-json-token"),
    ),
    (
        "Authorization: Bearer synthetic-header-token-123456\nX-Api-Key: synthetic-api-key",
        ("synthetic-header-token-123456", "synthetic-api-key"),
    ),
    (
        "first line\npassword = synthetic-multiline-password\nlast line",
        ("synthetic-multiline-password",),
    ),
    (
        "fetch https://support-user:synthetic-url-password@example.test/private",
        ("support-user", "synthetic-url-password"),
    ),
    (
        "dodo_live_syntheticprovidertoken123 gumroad_secret_syntheticprovidertoken456 sbp_syntheticprovidertoken789",
        ("dodo_live_syntheticprovidertoken123", "gumroad_secret_syntheticprovidertoken456",
         "sbp_syntheticprovidertoken789"),
    ),
])
def test_redact_text_removes_synthetic_secret_forms(text, private_values):
    redacted = bundle.redact_text(text)
    for value in private_values:
        assert value not in redacted


def test_job_summary_is_allowlisted_and_omits_user_content():
    private_transcript = "synthetic private customer transcript"
    private_token = "synthetic-job-token"
    row = {
        "id": "a1b2c3d4e5f6", "stage": "error", "error_code": "TRANSCRIBE_TIMEOUT",
        "timings": {"transcribe": 1.2, "customer_note": 1.0},
        "completed_stages": ["downloading", private_transcript], "created_at": 100.0,
        "progress": 0.5, "input_type": "upload", "max_clips": 2,
        "url": f"https://user:{private_token}@private.example/video",
        "error": f"Transcript: {private_transcript}", "user_id": "customer@example.test",
        "source_path": "C:/Users/customer/private.mp4",
    }
    safe = bundle._redact_job(row)
    assert set(safe) <= bundle.APPROVED_JOB_FIELDS
    serialised = json.dumps(safe)
    for value in (private_transcript, private_token, "customer@example.test", "private.mp4"):
        assert value not in serialised
    assert safe["timings"] == {"transcribe": 1.2}
    assert safe["completed_stages"] == ["downloading"]
    assert "error_summary" not in safe and "url_host" not in safe


def test_diagnostics_env_and_logs_are_allowlisted(monkeypatch, tmp_path):
    private_value = "synthetic-environment-secret"
    monkeypatch.setenv("CLPZ_DEBUG", private_value)
    monkeypatch.setenv("CLPZ_CUSTOMER_EMAIL", "customer@example.test")
    summary = bundle.env_summary()
    assert summary["CLPZ_DEBUG"] == "[SET]"
    assert "CLPZ_CUSTOMER_EMAIL" not in summary
    assert set(summary) <= set(bundle.APPROVED_ENV_NAMES)

    raw = {
        "platform": "Windows", "python": "3.12.0", "cpu_count": 8,
        "unexpected": private_value, "error": "Transcript: private speech",
    }
    assert bundle.sanitize_diagnostics(raw) == {
        "platform": "Windows", "python": "3.12.0", "cpu_count": 8,
    }

    (tmp_path / "server_stdout.log").write_text(
        f"Authorization: Bearer {private_value}\nTranscript: private speech",
        encoding="utf-8",
    )
    metadata = bundle.log_metadata(tmp_path)
    assert metadata["server_stdout.log"]["present"] is True
    assert private_value not in json.dumps(metadata)
    assert "Transcript" not in json.dumps(metadata)


def test_main_bundle_contains_no_unapproved_text(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "server_stderr.log").write_text(
        "password=synthetic-output-password\nTranscript: private customer words",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    monkeypatch.setenv("CLIPFORGE_DATA", str(data_dir))
    monkeypatch.setenv("CLPZ_DEBUG", "synthetic-debug-value")
    monkeypatch.setattr(bundle, "machine_profile", lambda: {"platform": "TestOS"})
    monkeypatch.setattr(bundle, "collect_from_api", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["support_bundle.py", "--out", str(out_dir)])

    assert bundle.main() == 0
    payload = json.loads(next(out_dir.glob("*.json")).read_text(encoding="utf-8"))
    rendered = json.dumps(payload)
    for value in ("synthetic-output-password", "private customer words", "synthetic-debug-value"):
        assert value not in rendered
    assert "log_tails" not in payload
    assert payload["log_metadata"]["server_stderr.log"]["present"] is True


def test_live_bundle_never_echoes_api_url_credentials(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    monkeypatch.setattr(bundle, "machine_profile", lambda: {"platform": "TestOS"})
    monkeypatch.setattr(bundle, "collect_from_api", lambda *_: {"diagnostics": {}, "jobs": []})
    monkeypatch.setattr(
        sys, "argv",
        ["support_bundle.py", "--api", "https://support-user:synthetic-api-password@example.test", "--out", str(out_dir)],
    )

    assert bundle.main() == 0
    rendered = next(out_dir.glob("*.json")).read_text(encoding="utf-8")
    assert "support-user" not in rendered
    assert "synthetic-api-password" not in rendered
    assert '"source": "live API"' in rendered
