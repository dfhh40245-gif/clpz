# Run the doctor: `python scripts/doctor.py`
"""CLPZ doctor — prerequisite and environment checker.

Verifies the tools a developer or release machine needs WITHOUT exposing
secrets or contacting account/payment services. Exit code 0 = all required
checks pass; 1 = at least one required check failed; 2 = usage error.

Usage:
    python scripts/doctor.py [--json] [--scope {backend,full}]

``backend`` checks only the prerequisites needed for the backend test suite.
``full`` (the default) also requires Node.js and npm for the two JavaScript
applications.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Versions chosen to match the manifests and the tested environment (VERIFY.md).
MIN_PYTHON = (3, 12)
MIN_NODE = (22, 0)
FFMPEG_MIN = (4, 0)

results: list[dict] = []


def add(name: str, ok: bool, detail: str = "", required: bool = True) -> bool:
    results.append({"name": name, "ok": bool(ok), "required": required, "detail": detail})
    return ok


def _version_tuple(text: str) -> tuple:
    parts = []
    for chunk in text.strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def check_python() -> None:
    v = sys.version_info
    ok = v >= MIN_PYTHON
    add("python>=3.12", ok, f"{v.major}.{v.minor}.{v.micro}")


def check_node(required: bool) -> None:
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        add("node>=22+npm", False,
            "Node.js/npm not found on PATH — frontend-app and website builds unavailable",
            required=required)
        return
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True,
                             timeout=15).stdout.strip().lstrip("v")
        add("node>=22+npm", _version_tuple(out) >= MIN_NODE, f"node {out}")
    except Exception as exc:  # pragma: no cover
        add("node>=22+npm", False, f"node --version failed: {exc}", required=required)


def _probe_exe(label: str, exe: str, args: list[str], marker: str) -> None:
    found = shutil.which(exe)
    bundled = BACKEND / "bin" / (exe + (".exe" if os.name == "nt" else ""))
    path = found or (str(bundled) if bundled.exists() else None)
    if not path:
        add(label, False, f"{exe} not found on PATH or backend/bin")
        return
    try:
        proc = subprocess.run([path, *args], capture_output=True, text=True, timeout=60)
        output = (proc.stdout + proc.stderr)
        add(label, proc.returncode == 0 and marker in output.lower(),
            f"{path} rc={proc.returncode}")
    except Exception as exc:
        add(label, False, f"{path} failed: {exc}")


def check_media_tools() -> None:
    _probe_exe("ffmpeg-executes", "ffmpeg", ["-version"], "ffmpeg")
    _probe_exe("ffprobe-executes", "ffprobe", ["-version"], "ffprobe")
    # Known defect (F15): the bundled yt-dlp.exe exits 1 with no output.
    # The Python module must still work so the pipeline can run.
    try:
        import yt_dlp  # noqa: F401
        ver = metadata.version("yt-dlp")
        add("yt-dlp-python-module", True, ver)
    except Exception as exc:
        add("yt-dlp-python-module", False, f"import failed: {exc}")
    exe = BACKEND / "bin" / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    if exe.exists():
        try:
            proc = subprocess.run([str(exe), "--version"], capture_output=True,
                                  text=True, timeout=60)
            add("yt-dlp-bundled-exe", proc.returncode == 0 and bool(proc.stdout.strip()),
                f"rc={proc.returncode} — known defect F15, downloader falls back to the "
                "working Python module; task 13 must replace this binary"
                if proc.returncode != 0 else proc.stdout.strip(),
                required=False)
        except Exception as exc:
            add("yt-dlp-bundled-exe", False, f"failed: {exc}", required=False)
    else:
        add("yt-dlp-bundled-exe", False, "backend/bin/yt-dlp.exe missing", required=False)


def check_python_packages() -> None:
    missing = []
    lock_versions: dict[str, str] = {}
    try:
        lock = (BACKEND / "requirements.lock").read_text(encoding="utf-8")
        for line in lock.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            name, version = line.split("==", 1)
            lock_versions[name.lower().replace("_", "-")] = version

        for filename in ("requirements.txt", "requirements-dev.txt"):
            req = (BACKEND / filename).read_text(encoding="utf-8")
            for line in req.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(("-", "--")):
                    continue
                name = line.split(">=")[0].split("==")[0].split("<")[0].split(";")[0].strip()
                # Extras are part of the requirement (uvicorn[standard]) but not
                # of the installed distribution name.
                dist_name = name.split("[")[0].strip()
                normalized = dist_name.lower().replace("_", "-")
                expected = lock_versions.get(normalized)
                if not expected:
                    missing.append(f"{dist_name} (not pinned in requirements.lock)")
                    continue
                try:
                    actual = metadata.version(dist_name)
                    if actual != expected:
                        missing.append(f"{dist_name}=={expected} (installed {actual})")
                except metadata.PackageNotFoundError:
                    missing.append(f"{dist_name}=={expected}")
    except OSError as exc:
        add("backend-deps-locked", False, f"cannot read manifest: {exc}")
        return
    add("backend-deps-locked", not missing,
        "all runtime/test roots installed at locked versions" if not missing
        else f"missing or mismatched: {', '.join(missing)}")


def check_disk_and_data() -> None:
    free_gb = None
    try:
        usage = shutil.disk_usage(ROOT)
        free_gb = usage.free / 1024**3
        add("free-disk>=2GiB", free_gb >= 2.0, f"{free_gb:.1f} GiB free")
    except Exception as exc:
        add("free-disk>=2GiB", False, f"disk usage failed: {exc}")
    data_dir = Path(os.environ.get("CLIPFORGE_DATA") or (BACKEND / "data"))
    try:
        if data_dir.exists():
            # Existing data dir: only drop a probe file, never touch its contents.
            probe = data_dir / ".doctor-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            add("data-dir-writable", True, str(data_dir))
        else:
            # Not created yet: probe the nearest existing parent so the doctor
            # never creates the real application data directory as a side effect.
            parent = data_dir.parent
            while not parent.exists():
                parent = parent.parent
            probe = parent / f".doctor-write-probe-{os.getpid()}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            add("data-dir-writable", True, f"{data_dir} (new; parent {parent} writable)")
    except OSError as exc:
        add("data-dir-writable", False, f"{data_dir}: {exc}")


def check_model_status() -> None:
    # Model download is deferred to first use; report, don't require.
    cache = Path.home() / ".cache" / "huggingface"
    present = cache.exists() and any(cache.rglob("*.bin")) or any(
        (BACKEND / "models").glob("*")) if (BACKEND / "models").exists() else False
    add("whisper-model-status", True,
        "cached model assets found" if present
        else "no local model cache yet (downloads on first transcription)")


def main() -> int:
    parser = argparse.ArgumentParser(description="CLPZ prerequisite checker")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--scope", choices=("backend", "full"), default="full",
                        help="backend tests only or every local check (default: full)")
    args = parser.parse_args()

    check_python()
    check_node(required=args.scope == "full")
    check_media_tools()
    check_python_packages()
    check_disk_and_data()
    check_model_status()

    failed_required = [r for r in results if r["required"] and not r["ok"]]
    report = {"scope": args.scope, "ok": not failed_required,
              "failed_required": [r["name"] for r in failed_required],
              "checks": results}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in results:
            mark = "PASS" if r["ok"] else ("WARN" if not r["required"] else "FAIL")
            print(f"[{mark}] {r['name']}: {r['detail']}")
        print(f"\nDoctor: {'OK' if report['ok'] else 'FAILED — see above'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
