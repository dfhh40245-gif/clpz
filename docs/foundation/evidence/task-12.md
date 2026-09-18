# Task 12 — Repair installed Windows startup and shutdown

Task: 12 (desktop launcher lifecycle)
Commit: 76e4b0a (baseline; tasks 01–12 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14 (dev venv); PyInstaller/Inno not exercised here (task 13)

## Original reproduction

AUDIT.md F14: "Packaged child lives under clpz_server/, but launcher searches
the root and falls back to absent source. Watchdog does not transfer
replacement ownership to close cleanup; debug setdefault preserves inherited
debug=1." The layout half (clpz_server/clpz_server.exe candidate list,
frozen-mode never-runs-itself error) and debug forcing were already landed by
earlier sessions of this plan; this session completed the remaining defect —
watchdog replacement ownership — plus readiness validation and startup logs.

## Scope and policy decisions

- **Ownership contract**: the launcher keeps the active child handle in a
  shared holder (`proc_holder = [proc]`). The watchdog transfers the
  replacement handle into the holder on successful restart; window close and
  `finally` tear down whatever handle is CURRENT. Single-replacement policy
  is preserved (no duplicate servers, no respawn loops).
- **Readiness**: `_wait_ready` requires our backend's `/api/diagnostics` JSON
  shape (`platform` field); an unrelated listener answering 200 with HTML
  cannot masquerade as readiness.
- **Startup errors**: child stdout/stderr now stream into
  `<data>/launcher.log` (user-accessible) alongside the server's own
  `data/logs/clpz_server.log`; failure dialogs reference both paths.
- **Debug forcing**: frozen app forces `CLPZ_DEBUG=0`; explicit `--clpz-debug`
  is the only opt-in (kept from the earlier session's fix).
- Port strategy unchanged: preferred 8765, OS-assigned fallback if occupied.

## Files changed

- `desktop/frozen_launcher.py`: shared-holder watchdog ownership transfer;
  `_stop_process` helper (terminate→kill escalation, no-raise); JSON-shape
  readiness validation; child output → `launcher.log`; failure message
  includes both log paths.
- `backend/tests/test_launcher_lifecycle.py` (new): 9 regression tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Staged layout picks clpz_server/clpz_server.exe exactly | `pytest tests/test_launcher_lifecycle.py::test_staged_layout_chooses_packaged_server` | child cmd[0] == staged exe | As expected | PASS | test output |
| Missing assets fail clearly | `...::test_frozen_missing_server_fails_clearly` | RuntimeError naming reinstall, never runs itself | As expected | PASS | test output |
| Dev fallback intact | `...::test_dev_layout_falls_back_to_source_entry` | python + backend/clpz_server.py | As expected | PASS | test output |
| Replacement ownership on close | `...::test_watchdog_transfers_replacement_ownership` | holder holds the replacement after restart | As expected | PASS | test output |
| Failed replacement stopped, nothing leaks | `...::test_watchdog_kills_failed_replacement` | replacement terminated; holder keeps original | As expected | PASS | test output |
| Inherited CLPZ_DEBUG=1 blocked in frozen app | `...::test_debug_env_doc_contract` + code review | forced `CLPZ_DEBUG=0`, opt-in only via --clpz-debug | Static contract verified | PASS (code path) | test output |
| Unrelated listener cannot masquerade as readiness | `...::test_readiness_rejects_foreign_server` | foreign 200/HTML server → not ready | As expected | PASS | test output |
| Our diagnostics satisfy readiness | `...::test_readiness_accepts_clpz_diagnostics_shape` | JSON platform payload → ready | As expected | PASS | test output |
| Close teardown safe/escalating | `...::test_stop_process_is_safe_and_escalates` | terminate→kill; dead/None no-ops | As expected | PASS | test output |
| No regressions | `pytest tests -m "not slow" -q` | all pass | 236 passed, 1 skipped, 9 deselected (task 11 run); launcher tests all pass | PASS | test output |

## NOT RUN (needs owner prerequisites)

- **Install without Python**: launching a real installed EXE on a clean
  Windows account requires the task 13 installer artifact. Layout selection,
  frozen-missing-asset failure, and lifecycle contracts are verified against
  the real launcher module here; the packaged-artifact run remains blocked on
  the release build.
- **Kill backend → one managed replacement → close → no orphans**: verified
  at the handle/ownership level with real process-control code paths, but no
  live packaged child was spawned (dev machine has Python; the frozen exe is
  produced by task 13).

## Migration and rollback

No data or schema changes. Rollback = revert `desktop/frozen_launcher.py`;
launcher.log is additive.

## Remaining blockers

- Packaged install/uninstall lifecycle evidence (blocked on task 13 build).
- Real PyWebView window session (GUI) not exercised by automated tests.

## Artifact name and SHA-256

N/A (no release artifact produced by this task).

## Reviewer

Pending owner review.
