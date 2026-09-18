"""CLPZ frozen-app server entry point.

When packaged with PyInstaller there is no python.exe to spawn, so the
backend runs in-process inside this executable. main.py imports cleanly
(module-level FastAPI app, no __main__ block), so a plain import starts
everything: config, database migrations, job restore, routes.

Usage:
    clpz_server.exe serve --port 8765
    clpz_server.exe freeze-bootstrap <model_dir>   (run once at build time)
"""
import argparse
import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Install root: the folder containing bin/, data/, frontend/, models/.

    The server exe lives in <install>/clpz_server/, so if bin/ is not next to
    the exe, use the parent directory (the actual install root).
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    if (base / "bin").is_dir():
        return base
    if (base.parent / "bin").is_dir():
        return base.parent
    return base


def _data_dir(base: Path) -> Path:
    """User-data dir. Never inside Program Files (not writable).

    Order: CLIPFORGE_DATA env > %LOCALAPPDATA%/CLPZ/data > base/data.
    """
    env = os.environ.get("CLIPFORGE_DATA")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        p = Path(local_app) / "CLPZ" / "data"
        try:
            p.mkdir(parents=True, exist_ok=True)
            # verify actually writable (Program Files virtualization can lie)
            probe = p / ".write_test"
            probe.touch(); probe.unlink()
            return p
        except OSError:
            pass
    p = base / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _setup_logging(data: Path) -> None:
    """Configure structured, rotating file logging (data/clpz_server.log)
    plus console output.  Never logs credentials or session tokens."""
    import logging
    from logging.handlers import RotatingFileHandler

    log_dir = data / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    file_h = RotatingFileHandler(
        log_dir / "clpz_server.log", maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8",
    )
    file_h.setFormatter(fmt)
    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_h)
    root.addHandler(console_h)
    # Don't duplicate uvicorn's own access logs on the console
    logging.getLogger("uvicorn.access").addHandler(console_h)
    logging.getLogger("uvicorn.error").propagate = False
    logging.getLogger("uvicorn.error").addHandler(file_h)
    logging.getLogger("uvicorn.error").addHandler(console_h)
    logging.getLogger("clpz.api").info("CLPZ server logging initialized (log dir: %s)", log_dir)


def _prepare_env(port: int) -> None:
    base = _base_dir()
    data = _data_dir(base)
    _setup_logging(data)

    os.environ.setdefault("CLIPFORGE_DATA", str(data))
    # Bundled binaries live in <install>/bin
    bin_dir = base / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    # Production behaviour: never expose dev backdoors in the packaged app
    os.environ.setdefault("CLPZ_DEBUG", "0")

    # Frontend layout inside the installed package
    os.environ.setdefault("CLIPFORGE_FRONTEND_DIR", str(base / "frontend"))
    os.environ.setdefault("CLIPFORGE_REACT_DIR", str(base / "frontend-app-dist"))

    # Whisper models: bundled (offline) or downloaded on first run
    model_dir = base / "models"
    if model_dir.exists():
        os.environ.setdefault("CLIPFORGE_MODEL_DIR", str(model_dir))

    # Nothing external should be needed; keep imports local
    sys.path.insert(0, str(base / "_internal"))
    sys.path.insert(0, str(base / "backend"))

    # Imported AFTER env setup so config picks up the packaged paths.
    import logging
    import main  # noqa: E402  (starts migrations, restores jobs)

    import uvicorn  # noqa: E402
    logging.getLogger("clpz.api").info("CLPZ server starting on 127.0.0.1:%s", port)
    # proxy_headers=False: uvicorn must NOT rewrite request.client from
    # X-Forwarded-For for loopback peers, or rate limiting could be spoofed.
    # Trusted forwarding is handled explicitly by CLPZ_TRUSTED_PROXIES.
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning",
                proxy_headers=False)


def _freeze_bootstrap(model_dir: str) -> None:
    """Build-time helper: pre-download the Whisper model into the package."""
    os.environ["CLIPFORGE_MODEL_DIR"] = model_dir
    from faster_whisper.utils import download_model

    path = download_model(os.environ.get("WHISPER_MODEL", "tiny"), output_dir=model_dir)
    print(f"model ready: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="clpz_server")
    sub = ap.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    boot = sub.add_parser("freeze-bootstrap")
    boot.add_argument("model_dir")
    args = ap.parse_args()

    if args.cmd == "serve":
        _prepare_env(args.port)
    elif args.cmd == "freeze-bootstrap":
        _freeze_bootstrap(args.model_dir)


if __name__ == "__main__":
    # R02: the pipeline spawns a supervised transcription child via
    # multiprocessing spawn. In a frozen exe the child re-executes this
    # entry point, so freeze_support() must run before anything else —
    # otherwise the spawned child would boot the whole server again.
    import multiprocessing

    multiprocessing.freeze_support()
    main()
