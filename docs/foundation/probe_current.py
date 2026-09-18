"""Audit probes, not application fixes. Run with the backend test dependencies.

Uses a new temporary data directory, fake accounts, and generated media only.
Never reads .env files or connects to payment/account providers.
Writes evidence beside this script; keeps temporary media for inspection.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(tempfile.mkdtemp(prefix="clpz-foundation-probe-"))
os.environ.update(CLIPFORGE_DATA=str(DATA), CLIPFORGE_CLIPS_DIR=str(DATA / "exports"),
                  CLPZ_DEBUG="0", CLPZ_DISABLE_MAINTENANCE="1",
                  CLPZ_ADMIN_EMAIL="foundation-owner@example.com", RESEND_API_KEY="")
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

import main
import jobs
import credits
import database as db
from fastapi.testclient import TestClient
from pipeline.transcriber import _merge_chunks
from desktop import frozen_launcher

results = {"data_directory": str(DATA), "python": sys.version.split()[0]}


def record(name, callback):
    try:
        results[name] = callback()
    except Exception as exc:
        results[name] = {"probe_error": type(exc).__name__, "message": str(exc)[:600]}


with TestClient(main.app, raise_server_exceptions=False) as client:
    signup = client.post("/api/auth/signup", json={
        "email": "foundation-owner@example.com", "password": "FoundationTest123"})
    signup.raise_for_status()
    uid = signup.json()["user"]["id"]
    results["admin_bootstrap"] = {
        "email_verified": signup.json()["email_verified"],
        "admin_status": client.get("/api/admin/users").status_code,
    }
    results["password_reset_throttle"] = [client.post("/api/auth/reset", json={
        "email": "foundation-owner@example.com", "current_password": "wrong",
        "new_password": "FoundationOther123"}).status_code for _ in range(15)]
    credits.refund(uid, 1, related_id="foundation-refund")
    record("duplicate_refund", lambda: credits.refund(uid, 1, related_id="foundation-refund"))

    with patch.object(jobs, "_run", lambda *a: None):
        first = client.post("/api/jobs", json={"url": "https://youtube.com/watch?v=audit",
                                               "idempotency_key": "foundation-shared"})
        client.cookies.clear()
        second = client.post("/api/jobs", json={"url": "https://youtube.com/watch?v=other",
                                                "idempotency_key": "foundation-shared"})
        results["cross_owner_replay"] = {
            "same_job": first.json().get("job_id") == second.json().get("job_id"),
            "anonymous_status": second.status_code,
            "anonymous_read_status": client.get("/api/jobs/" + first.json()["job_id"]).status_code,
        }
        jid = client.post("/api/jobs", json={"url": "https://youtube.com/watch?v=audit"}).json()["job_id"]
        results["local_boundary"] = {
            "untrusted_origin_cancel": client.post(f"/api/jobs/{jid}/cancel",
                headers={"Origin": "https://untrusted.example"}).status_code,
            "untrusted_host_list": client.get("/api/jobs", headers={"Host": "untrusted.example"}).status_code,
        }

    jid = jobs.create_upload_job("audit.mp4", 1)
    video = DATA / jid / "clip_0.mp4"
    subprocess.run([jobs._find_bin("ffmpeg"), "-v", "error", "-y", "-f", "lavfi",
        "-i", "color=c=blue:s=1080x1920:d=1", "-f", "lavfi", "-i",
        "sine=frequency=300:duration=1", "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-shortest", str(video)], check=True, capture_output=True, timeout=30)
    jobs._update(jid, stage="done", clips=[{"index": 0, "status": "done", "file": str(video),
                                          "title": "Audit", "start": 0, "end": 1}])
    for name, body in [("normal", {}), ("muted", {"muted": True}), ("quarter_speed", {"speed": .25})]:
        response = client.post(f"/api/jobs/{jid}/clips/0/edit", json=body)
        results["export_" + name] = {"status": response.status_code,
                                    "detail": response.json().get("detail", "success")}

    retry_id = jobs.create_upload_job("retry.mp4", 1)
    (DATA / retry_id / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello world.\n", encoding="utf-8")
    jobs._update(retry_id, video={"path": str(video), "duration": 1, "title": "Retry"},
                 completed_stages=["download", "transcribe", "parse", "analyze"])
    jobs._run_pipeline(retry_id)
    retried = jobs.get_job(retry_id)
    results["retry_after_analysis"] = {"stage": retried["stage"], "error": retried.get("error")}

chunk = {"segments": [{"start": 28, "end": 29, "text": "hello world"}], "words": [
    {"word": "hello", "start": 28, "end": 28.5}, {"word": "world", "start": 28.5, "end": 29}]}
merged = _merge_chunks([chunk, chunk], 60)
results["overlap"] = {"expected_words": 2, "actual_words": len(merged["words"]),
                      "actual_segments": len(merged["segments"])}
record("first_backup", lambda: str(db.backup_database()))
record("second_backup", lambda: str(db.backup_database()))

# Emulate the exact package layout without building or executing an EXE.
base = DATA / "package"
(base / "clpz_server").mkdir(parents=True)
(base / "clpz_server" / "clpz_server.exe").touch()
with patch.object(frozen_launcher.subprocess, "Popen") as popen:
    frozen_launcher._spawn_server(base, 8765, {})
    command = popen.call_args.args[0]
    results["packaged_launcher_path"] = {
        "expected_executable": str(base / "clpz_server" / "clpz_server.exe"),
        "actual_command": command, "matched": command[0] == str(base / "clpz_server" / "clpz_server.exe")}
db.close()
output = Path(__file__).resolve().parent / "evidence" / "current-probes.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
