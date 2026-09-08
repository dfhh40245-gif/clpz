"""Isolated audit probes; does not use the application's existing data."""
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(tempfile.mkdtemp(prefix="clpz-audit-", dir=ROOT / "backend"))
os.environ["CLIPFORGE_DATA"] = str(DATA)
os.environ["CLIPFORGE_CLIPS_DIR"] = str(DATA / "exports")
os.environ["CLPZ_DEBUG"] = "0"
os.environ["CLPZ_DISABLE_MAINTENANCE"] = "1"
os.environ["CLPZ_ADMIN_EMAIL"] = "audit-owner@example.com"
sys.path.insert(0, str(ROOT / "backend"))
import main
import jobs
import credits
import database as db
from fastapi.testclient import TestClient

results = {}
with TestClient(main.app, raise_server_exceptions=False) as client:
    signup = client.post("/api/auth/signup", json={"email": "audit-owner@example.com", "password": "AuditPass123"})
    uid = signup.json()["user"]["id"]
    results["unverified_admin"] = {"verified": signup.json()["email_verified"], "admin_status": client.get("/api/admin/users").status_code}
    attempts = [client.post("/api/auth/reset", json={"email": "audit-owner@example.com", "current_password": "wrong", "new_password": "AuditPass456"}).status_code for _ in range(15)]
    results["reset_bruteforce"] = {"attempts": len(attempts), "statuses": sorted(set(attempts))}
    credits.refund(uid, 1, related_id="audit-refund")
    try:
        credits.refund(uid, 1, related_id="audit-refund")
        results["duplicate_refund"] = "no error"
    except Exception as exc:
        results["duplicate_refund"] = repr(exc)
    with patch.object(jobs, "_run", lambda *a: None):
        first = client.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=audit", "idempotency_key": "shared-audit-key"})
        client.cookies.clear()
        second = client.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=different", "idempotency_key": "shared-audit-key"})
        results["cross_user_idempotency"] = {"same_job": first.json()["job_id"] == second.json()["job_id"], "anonymous_status": second.status_code, "read_status": client.get('/api/jobs/' + second.json()['job_id']).status_code}
        anon = client.post("/api/jobs", json={"url": "https://www.youtube.com/watch?v=audit"})
        jid = anon.json()["job_id"]
        results["anonymous_jobs"] = {"create_status": anon.status_code, "credits_remaining": anon.json()["credits_remaining"], "cross_origin_cancel_status": client.post(f"/api/jobs/{jid}/cancel", headers={"Origin": "https://untrusted.example"}).status_code, "arbitrary_host_status": client.get("/api/jobs", headers={"Host": "untrusted.example"}).status_code}
    jid = jobs.create_upload_job("audit.mp4", 1)
    video = DATA / jid / "clip_0.mp4"
    cmd = [jobs._find_bin("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=1", "-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(video)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    jobs._update(jid, stage="done", clips=[{"index":0,"status":"done","file":str(video),"title":"Audit","start":0,"end":1}])
    for name, body in [("normal", {}), ("muted", {"muted":True}), ("quarter_speed", {"speed":0.25}), ("apostrophe", {"text_overlays":[{"text":"It's working"}]})]:
        response = client.post(f"/api/jobs/{jid}/clips/0/edit", json=body)
        results["edit_" + name] = {"status": response.status_code, "detail":response.json().get("detail", "success")}
    from pipeline.transcriber import _merge_chunks
    words = [{"word":"hello", "start":28.0, "end":28.5},{"word":"world", "start":28.5, "end":29.0}]
    chunk = {"segments":[{"start":28,"end":29,"text":"hello world"}], "words":words}
    merged = _merge_chunks([chunk, chunk], 60)
    results["overlap_merge"] = {"expected_words":2, "actual_words":len(merged["words"]), "actual_segments":len(merged["segments"])}
db.close()
output = ROOT / "docs" / "audit-reproduction-results.json"
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
print("Isolated artifacts:", DATA)
