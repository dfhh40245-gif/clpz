"""Benchmark the existing speech fixture in an isolated local server."""
import os, sys, json, time, tempfile, subprocess
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
data = Path(tempfile.mkdtemp(prefix="clpz-pipeline-audit-", dir=ROOT / "backend"))
env = os.environ.copy()
env.update(CLIPFORGE_DATA=str(data), CLIPFORGE_CLIPS_DIR=str(data / "exports"), CLPZ_DISABLE_MAINTENANCE="1", CLPZ_DEBUG="0")
base = "http://127.0.0.1:8129"
log = (data / "server.log").open("w")
p = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8129", "--log-level", "warning"], cwd=ROOT / "backend", env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
try:
    for _ in range(50):
        try:
            requests.get(base + "/api/jobs", timeout=1).raise_for_status()
            break
        except requests.RequestException:
            time.sleep(0.2)
    start = time.perf_counter()
    with (ROOT / "backend/tests/fixtures/test_video_20s.mp4").open("rb") as f:
        r = requests.post(base + "/api/jobs/upload", files={"file":("audit-speech.mp4", f, "video/mp4")}, data={"max_clips":"1"}, timeout=30)
    r.raise_for_status()
    jid = r.json()["job_id"]
    for _ in range(120):
        job = requests.get(base + "/api/jobs/" + jid, timeout=15).json()
        if job["stage"] in ("done", "error", "cancelled"):
            break
        time.sleep(1)
    result = {"elapsed_seconds":round(time.perf_counter()-start,2), "stage":job["stage"], "error":job.get("error"), "timings":job.get("timings"), "data_dir":str(data), "clips":[{"status":c["status"],"duration":c.get("duration"),"error":c.get("error"),"validation":c.get("validation")} for c in job.get("clips",[])]}
    if job["stage"] == "done":
        clip = job["clips"][0]
        media = requests.get(base + clip["stream_url"], headers={"Range":"bytes=0-99"}, timeout=10)
        result["media_range"] = {"status":media.status_code,"bytes":len(media.content),"content_range":media.headers.get("content-range")}
    (ROOT / "docs/audit-pipeline-results.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2), flush=True)
finally:
    p.terminate()
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    log.close()
