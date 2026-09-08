"""Reproduce the packaged-server render failure with full stderr capture."""
import sys, json, subprocess
sys.path.insert(0, r"C:\Users\oSSS\Desktop\clpz-actual\backend")
import os
os.chdir(r"C:\Users\oSSS\Desktop\clpz-actual\backend")
jid = json.load(open(r"C:\Users\oSSS\AppData\Local\Temp\pkg_job3.json"))["job_id"]
D = rf"C:\Users\oSSS\AppData\Local\Temp\pb_pkg_data\{jid}"
from pipeline import cutter
import config

plan = cutter.plan_layout(D + r"\source.mp4", 5.0, 25.0)
src_w, src_h = plan["src_w"], plan["src_h"]
print("plan mode:", plan.get("mode"), "src:", src_w, "x", src_h)

ass_path = (D + r"\clip_0.ass").replace("\\", "/").replace(":", "\\:")
vf = f"crop={src_w}:{src_h}:0:0,scale={config.OUT_WIDTH}:{config.OUT_HEIGHT}:flags=lanczos"
vf += f",ass='{ass_path}'"
cmd = [cutter._find_bin("ffmpeg"), "-y", "-ss", "5.00", "-to", "25.00", "-i", D + r"\source.mp4",
       "-vf", vf, "-c:v", "libx264", "-preset", config.VIDEO_PRESET, "-crf", str(config.VIDEO_CRF),
       "-profile:v", config.VIDEO_PROFILE, "-level:v", config.VIDEO_LEVEL,
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
       D + r"\repro.mp4"]
print("VF:", vf[:200])
r = subprocess.run(cmd, capture_output=True, timeout=120, text=False)
err = (r.stderr or b"").decode("utf-8", errors="replace")
print("rc:", r.returncode)
lines = [l for l in err.splitlines() if l.strip()]
for l in lines[:20]:
    print(">", l[:160])
