"""Build the CLPZ Windows package (task 13: one reproducible release command).

Assembles:
    out/CLPZ/
        CLPZ.exe             (windowed launcher)
        clpz_server/         (PyInstaller onedir: clpz_server.exe + _internal)
        bin/                 (ffmpeg, ffprobe, yt-dlp, deno)
        frontend/            (vanilla HTML pages)
        frontend-app-dist/   (built React SPA)
        models/              (bundled faster-whisper tiny snapshot)

Every bundled executable must pass a version smoke check; the package audit
fails on missing tools, missing frontends, an empty/absent output tree, or
any secret hit. Produces RELEASE_SHA256.txt + release-manifest.json.

Usage:
    python packaging/build_windows.py [--skip-models] [--skip-build] [--audit-only]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "out" / "CLPZ"
DIST = ROOT / "packaging" / "dist"

# Centralized version: bump here (and only here) for a release.
APP_VERSION = os.environ.get("CLPZ_VERSION", "1.0.0")


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def _smoke_check(exe: Path, args: list[str], expect: str) -> None:
    """Run a version/smoke check on a bundled tool. Existence is not enough
    (F15: the old yt-dlp.exe existed but exited 1 on every machine without
    C:\\Python314). Raises SystemExit on failure so the build stops early."""
    if not exe.exists():
        raise SystemExit(f"BUNDLED TOOL MISSING: {exe}")
    try:
        r = subprocess.run(
            [str(exe), *args], capture_output=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        out = (r.stdout or b"") + (r.stderr or b"")
        if r.returncode != 0 or expect.encode() not in out.lower():
            raise SystemExit(
                f"BUNDLED TOOL BROKEN: {exe} rc={r.returncode} "
                f"output={out[:200]!r}"
            )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"BUNDLED TOOL HUNG: {exe}")
    print(f"  smoke OK: {exe.name}")


def smoke_check_bundled_tools() -> None:
    """Verify every tool we ship actually executes (task 13)."""
    print("Smoke-checking bundled tools...")
    bin_dir = ROOT / "backend" / "bin"
    _smoke_check(bin_dir / "ffmpeg.exe", ["-version"], "ffmpeg")
    _smoke_check(bin_dir / "ffprobe.exe", ["-version"], "ffprobe")
    _smoke_check(bin_dir / "yt-dlp.exe", ["--version"], "20")  # any 20xx version string
    deno = bin_dir / "deno.exe"
    if deno.exists():
        _smoke_check(deno, ["--version"], "deno")


def build_frontend() -> None:
    """Rebuild the React SPA (task 13: the release command must not ship a
    stale or manually copied frontend-app/dist)."""
    fa = ROOT / "frontend-app"
    if not (fa / "package.json").exists():
        raise SystemExit("frontend-app/package.json missing — cannot build UI")
    npm = shutil.which("npm")
    if npm is None:
        # Windows default location fallback
        candidate = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "nodejs" / "npm.cmd"
        npm = str(candidate) if candidate.exists() else None
    if npm is None:
        raise SystemExit(
            "npm not found on PATH — required to rebuild the React UI. "
            "Install Node.js or build frontend-app/dist manually and pass --skip-ui."
        )
    run([npm, "ci"], cwd=fa, shell=(os.name == "nt"))
    run([npm, "run", "build"], cwd=fa, shell=(os.name == "nt"))
    dist = fa / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("frontend build produced no dist/index.html")


def build_exes():
    # Valid spec-mode invocation: --specpath is set BY the spec discovery, and
    # dist/work dirs are explicit. Refuse stale output (task 13).
    if DIST.exists():
        shutil.rmtree(DIST)
    common = ["--noconfirm", "--distpath", DIST,
              "--workpath", ROOT / "packaging" / "build",
              "--specpath", ROOT / "packaging"]
    run([sys.executable, "-m", "PyInstaller", "packaging/clpz_server.spec", *common], cwd=ROOT)
    run([sys.executable, "-m", "PyInstaller", "packaging/clpz_launcher.spec", *common], cwd=ROOT)
    for required in (DIST / "CLPZ.exe", DIST / "clpz_server" / "clpz_server.exe"):
        if not required.exists():
            raise SystemExit(f"PyInstaller produced no {required.name} at {required.parent}")


def assemble(skip_models: bool, skip_ui: bool = False) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # Launchers (windowed EXE builds onefile-style to dist/CLPZ.exe)
    shutil.copy2(DIST / "CLPZ.exe", OUT / "CLPZ.exe")
    shutil.copytree(DIST / "clpz_server", OUT / "clpz_server")

    # Bundled binaries — REQUIRED (fail, not warn; task 13)
    (OUT / "bin").mkdir()
    for b in ("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe"):
        src = ROOT / "backend/bin" / b
        if not src.exists():
            raise SystemExit(f"REQUIRED bundled binary missing: {b}")
        shutil.copy2(src, OUT / "bin" / b)
    deno_src = ROOT / "backend/bin" / "deno.exe"
    if deno_src.exists():
        shutil.copy2(deno_src, OUT / "bin" / "deno.exe")

    # Frontends — REQUIRED and verified non-empty (task 13)
    frontend_src = ROOT / "frontend"
    if not any(frontend_src.glob("*.html")):
        raise SystemExit("frontend/ contains no HTML pages")
    shutil.copytree(frontend_src, OUT / "frontend")
    react_dist = ROOT / "frontend-app" / "dist"
    if not (react_dist / "index.html").exists():
        raise SystemExit(
            "frontend-app/dist/index.html missing — run the full build (do not "
            "pass --skip-ui) so the packaged UI is current."
        )
    if not skip_ui:
        build_frontend()
        # build_frontend recreated dist; re-copy it now
        if (OUT / "frontend-app-dist").exists():
            shutil.rmtree(OUT / "frontend-app-dist")
    shutil.copytree(react_dist, OUT / "frontend-app-dist")

    # Whisper model (tiny, ~75 MB) for offline first-run
    if not skip_models:
        import os
        os.environ.setdefault("WHISPER_MODEL", "tiny")
        model_dir = OUT / "models"
        model_dir.mkdir()
        run([sys.executable, str(ROOT / "backend/clpz_server.py"),
             "freeze-bootstrap", str(model_dir)], cwd=ROOT)
        if not any(model_dir.iterdir()):
            raise SystemExit("model bundle step produced an empty models/ directory")

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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_release_manifest() -> None:
    """Generate RELEASE_SHA256.txt + release-manifest.json for the exact
    assembled tree (task 13: hashes must correspond to the tested files)."""
    out_dir = ROOT / "packaging" / "out"
    files = sorted(p for p in OUT.rglob("*") if p.is_file())
    lines = []
    manifest = {
        "version": APP_VERSION,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "files": [],
    }
    for p in files:
        rel = p.relative_to(out_dir).as_posix()
        digest = _sha256(p)
        lines.append(f"{digest}  {rel}")
        manifest["files"].append({"path": rel, "sha256": digest,
                                  "size": p.stat().st_size})
    installer = out_dir / "CLPZ-Setup-Windows-x64.exe"
    if installer.exists():
        rel = installer.relative_to(out_dir).as_posix()
        digest = _sha256(installer)
        lines.append(f"{digest}  {rel}")
        manifest["installer"] = {"path": rel, "sha256": digest,
                                 "size": installer.stat().st_size}
    (out_dir / "RELEASE_SHA256.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written: {len(manifest['files'])} files hashed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true", help="reuse existing PyInstaller output")
    ap.add_argument("--skip-models", action="store_true", help="do not bundle the whisper model")
    ap.add_argument("--skip-ui", action="store_true", help="do not rebuild the React UI (dist must exist)")
    ap.add_argument("--audit-only", action="store_true", help="only run the package audit")
    args = ap.parse_args()

    if args.audit_only:
        # A missing/empty tree is a FAILURE, not a clean pass (task 13).
        if not OUT.exists() or not any(OUT.iterdir()):
            print("AUDIT FAILED: no assembled package at", OUT)
            raise SystemExit(1)
        smoke_check_bundled_tools()
        ok = audit_package()
        raise SystemExit(0 if ok else 1)

    smoke_check_bundled_tools()
    if not args.skip_build:
        build_exes()
    assemble(skip_models=args.skip_models, skip_ui=args.skip_ui)

    ok = audit_package()
    write_release_manifest()
    print(f"\nPackage ready: {OUT} (audit {'CLEAN' if ok else 'FAILED'})")
    print("Next: build the installer with Inno Setup (see packaging/clpz_installer.iss), "
          "then re-run --audit-only.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
