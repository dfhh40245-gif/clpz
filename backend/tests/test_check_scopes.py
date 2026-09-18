"""Regression tests for task 02 verification scopes (R07)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_scope_stops_when_doctor_fails(monkeypatch):
    check = _load_script("check")
    called = []
    monkeypatch.setattr(check, "run", lambda name, cmd, cwd: called.append((name, cmd)) or 1)
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 1
    assert called == [("doctor", [check.PY, "scripts/doctor.py", "--scope", "full", "--json"])]


def test_fast_scope_explicitly_records_frontend_skips(monkeypatch):
    check = _load_script("check")
    called, skipped = [], []
    monkeypatch.setattr(check, "run", lambda name, cmd, cwd: called.append((name, cmd)) or 0)
    monkeypatch.setattr(check, "skip", lambda name, detail: skipped.append((name, detail)))
    monkeypatch.setattr(sys, "argv", ["check.py", "--fast"])

    assert check.main() == 0
    assert called[0] == ("doctor", [check.PY, "scripts/doctor.py", "--scope", "backend", "--json"])
    assert [name for name, _ in skipped] == ["frontend-app", "website"]
    assert all("npm" not in command for _, command in called)


def test_full_scope_marks_missing_node_as_required(monkeypatch):
    doctor = _load_script("doctor")
    original_which = doctor.shutil.which
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None if name in {"node", "npm"} else original_which(name))
    doctor.results.clear()

    doctor.check_node(required=True)

    assert doctor.results == [{
        "name": "node>=22+npm",
        "ok": False,
        "required": True,
        "detail": "Node.js/npm not found on PATH — frontend-app and website builds unavailable",
    }]
