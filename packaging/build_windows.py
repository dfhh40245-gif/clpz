"""Build the CLPZ Windows package.

Assembles:
    out/CLPZ/
        CLPZ.exe             (windowed launcher)
        clpz_server/         (PyInstaller onedir: clpz_server.exe + _internal)
        bin/                 (ffmpeg, ffprobe, yt-dlp, deno)
        frontend/            (vanilla HTML pages)
        frontend-app-dist/   (built React SPA)
        models/              (bundled faster-whisper tiny snapshot)

Usage:
    python packaging/build_windows.py [--skip-models] [--skip-build] [--audit-only]
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "out" / "CLPZ"


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def build_exes():
    common = ["--noconfirm", "--distpath", ROOT / "packaging/dist",
              "--workpath", ROOT / "packaging/build",
              "--specpath", ROOT / "packaging"]
    run([sys.executable, "-m", "PyInstaller", "packaging/clpz_server.spec", *common], cwd=ROOT)
    run([sys.executable, "-m", "PyInstaller", "packaging/clpz_launcher.spec", *common], cwd=ROOT)


def assemble(skip_models: bool) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # Launchers (windowed EXE builds onefile-style to dist/CLPZ.exe)
    shutil.copy2(ROOT / "packaging/dist/CLPZ.exe", OUT / "CLPZ.exe")
    shutil.copytree(ROOT / "packaging/dist/clpz_server", OUT / "clpz_server")

    # Bundled binaries
    (OUT / "bin").mkdir()
    for b in ("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "deno.exe"):
        src = ROOT / "backend/bin" / b
        if src.exists():
            shutil.copy2(src, OUT / "bin" / b)
        else:
            print(f"WARNING: bundled binary missing: {b}")

    # Frontends
    shutil.copytree(ROOT / "frontend", OUT / "frontend")
    shutil.copytree(ROOT / "frontend-app/dist", OUT / "frontend-app-dist")

    # Whisper model (tiny, ~75 MB) for offline first-run
    if not skip_models:
        import os
        os.environ.setdefault("WHISPER_MODEL", "tiny")
        model_dir = OUT / "models"
        model_dir.mkdir()
        run([sys.executable, str(ROOT / "backend/clpz_server.py"),
             "freeze-bootstrap", str(model_dir)], cwd=ROOT)

    print("\nAssembled:", OUT)


def audit_package() -> bool:
    """Security/secret/AWS audit of the assembled package. Returns clean bool."""
    import re as _re

    issues = []

    aws = [p for p in OUT.rglob("*") if p.is_file() and ("boto3" in p.name.lower() or "botocore" in p.name.lower())]
    if aws:
        issues.append(f"AWS files: {[str(p.relative_to(OUT)) for p in aws[:5]]}")

    secret_patterns = [
        (_re.compile(rb"SUPABASE_SERVICE_ROLE|service_role"), "supabase service key ref"),
        (_re.compile(rb"sk-[a-zA-Z0-9]{20,}"), "api key literal"),
        (_re.compile(rb"re_[a-zA-Z0-9]{20,}"), "resend key literal"),
        (_re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
        (_re.compile(rb"eyJhbGciOi[A-Za-z0-9._-]{50,}"), "JWT/supabase key literal"),
    ]
    text_exts = {".py", ".json", ".txt", ".html", ".js", ".css", ".cfg", ".ini", ".yaml", ".yml", ".toml", ".md", ".bat", ".cmd", ".ps1", ""}
    scanned = 0
    for p in OUT.rglob("*"):
        if not p.is_file() or p.stat().st_size > 40 * 1024 * 1024:
            continue
        if p.suffix.lower() not in text_exts:
            continue  # binary blobs (dll/pyd) produce false positives on short patterns
        try:
            data = p.read_bytes()
        except OSError:
            continue
        scanned += 1
        for pat, label in secret_patterns:
            if pat.search(data):
                issues.append(f"{label}: {p.relative_to(OUT)}")

    for p in OUT.rglob("*"):
        if p.is_file() and (p.name.startswith(".env") or p.name == "cookies.txt" or "credential" in p.name.lower()):
            issues.append(f"sensitive file packaged: {p.relative_to(OUT)}")

    td = [p for p in OUT.rglob("*") if "test_data" in str(p)]
    if td:
        issues.append(f"test data in package: {[str(p.relative_to(OUT)) for p in td[:3]]}")

    print(f"audit: {scanned} files scanned")
    if issues:
        print("AUDIT ISSUES:")
        for i in issues:
            print(" -", i)
        return False
    print("AUDIT CLEAN: no secrets, no AWS, no test data")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true", help="reuse existing PyInstaller output")
    ap.add_argument("--skip-models", action="store_true", help="do not bundle the whisper model")
    ap.add_argument("--audit-only", action="store_true", help="only run the package audit")
    args = ap.parse_args()

    if args.audit_only:
        raise SystemExit(0 if audit_package() else 1)

    if not args.skip_build:
        build_exes()
    assemble(skip_models=args.skip_models)

    ok = audit_package()
    print(f"\nPackage ready: {OUT} (audit {'CLEAN' if ok else 'FAILED'})")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
