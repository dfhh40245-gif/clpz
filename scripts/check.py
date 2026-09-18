# One documented check command: `python scripts/check.py`
"""Run CLPZ local verification with an explicit scope.

Usage:
    python scripts/check.py [--fast | --backend-only]

No option runs the full backend, React, and website check. ``--fast`` and
``--backend-only`` both currently run the backend non-slow suite only; both
report the JavaScript surfaces as intentionally skipped. This is explicit so a
missing tool can never silently narrow the requested full check.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
results: list[dict[str, str]] = []


def run(name: str, cmd: list[str], cwd: Path) -> int:
    print(f"\n=== {name} ===\n$ {' '.join(cmd)}  (cwd={cwd})")
    proc = subprocess.run(cmd, cwd=str(cwd))
    status = "PASS" if proc.returncode == 0 else "FAIL"
    results.append({"name": name, "status": status, "detail": f"exit {proc.returncode}"})
    print(f"[{status}] {name} (exit {proc.returncode})")
    return proc.returncode


def skip(name: str, detail: str) -> None:
    results.append({"name": name, "status": "SKIP", "detail": detail})
    print(f"[SKIP] {name}: {detail}")


def report(scope: str) -> None:
    print(f"\n=== Check report ({scope}) ===")
    for item in results:
        print(f"[{item['status']}] {item['name']}: {item['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CLPZ local check runner")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fast", action="store_true", help="doctor + backend non-slow tests only")
    mode.add_argument("--backend-only", action="store_true", help="explicitly skip React and website checks")
    args = parser.parse_args()

    full_scope = not (args.fast or args.backend_only)
    scope = "full" if full_scope else "backend"

    # The full doctor requires npm. Missing it fails before any work begins.
    if run("doctor", [PY, "scripts/doctor.py", "--scope", scope, "--json"], ROOT) != 0:
        print("\nCheck FAILED at doctor. Fix prerequisites before running checks.")
        report(scope)
        return 1

    backend_tests = [PY, "-m", "pytest", "tests", "-m", "not slow", "-q", "--tb=short"]
    if run("backend-fast-tests", backend_tests, ROOT / "backend") != 0:
        report(scope)
        return 1

    if not full_scope:
        reason = "selected --fast" if args.fast else "selected --backend-only"
        skip("frontend-app", reason)
        skip("website", reason)
        report(scope)
        return 0

    # npm availability was already a required full-scope prerequisite.
    for prefix, commands in [
        ("frontend-app", [("react-build", "build"), ("react-tests", "test"), ("react-lint", "lint")]),
        ("website", [("website-build", "build"), ("website-lint", "lint")]),
    ]:
        if run(f"{prefix}-install", ["npm", "ci"], ROOT / prefix) != 0:
            report(scope)
            return 1
        for name, script in commands:
            if run(name, ["npm", "run", script], ROOT / prefix) != 0:
                report(scope)
                return 1

    report(scope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
