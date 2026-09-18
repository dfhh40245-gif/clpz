# Task 18 — Finish the desktop editor without losing existing work

Task: 18 (editor project contract)
Commit: 76e4b0a (baseline; tasks 01–18 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64); no browser-automation session available (visual checks manual)

## Original reproduction

AUDIT.md F23: "Active editor has draft/preview improvements, but text
overlays are not composited into preview and edit versions are not durable
backend projects." Confirmed: the editor listed overlays in a side panel
only (`renderTextOverlays` touched `#text-list`, never the preview), and
`edit_clip` returned only a filesystem path — choices died with the
localStorage draft.

## Scope and policy decisions

- **Shipping UI extended, not duplicated** (task 01 decision: vanilla /app
  is the desktop workspace): all changes are in `frontend/clpz.html` and the
  backend API. The unrouted React workspace was not touched (its retirement
  or completion is explicitly left as the documented open item; no second
  account surface was built).
- **Preview compositing**: text overlays are now drawn live over the preview
  via a pointer-events-none canvas positioned over the video. Export
  coordinates (1080×1920 output frame) are mapped into the letterbox-aware
  on-screen video box with devicePixelRatio scaling, so preview position =
  export position (within rendering tolerance). Overlays redraw on
  edit/undo/redo/restore/resize.
- **Durable edit versions**: every successful export persists an immutable
  `clpz.edit.v1` version record on the job (`edit_versions[]`): version id,
  schema tag, timestamp, clip index, immutable source reference
  (start/end/file), trim/speed/volume/mute, validated overlays, and export
  metadata (path, duration, has_audio). Original media is never modified.
  New `GET /api/jobs/{id}/edit-versions` lists them; the export response
  carries `edit_version` + `schema`.
- **Drafts preserved**: the existing localStorage draft system (v1 key
  format, clamped restore, malformed-JSON swallow) is unchanged; drafts
  still restore on reopen, and the durable backend version now survives
  beyond the device.
- Existing undo/redo history (50-deep, Ctrl+Z / Ctrl+Shift+Z), keyboard
  focus guards, and trim-bounded playback were retained as-is.

## Files changed

- `frontend/clpz.html`: overlay canvas + `drawOverlays()` (letterbox-aware
  coordinate mapping, DPR scaling, multi-line safe via split), redraw hooks
  in `syncPreview`/`renderTextOverlays`, hint copy updated.
- `backend/main.py`: `edit_clip` persists a versioned edit record
  (schema `clpz.edit.v1`) under `jobs._lock` + `_persist`; new
  `GET /api/jobs/{job_id}/edit-versions`; response includes
  `edit_version`/`schema`.
- No new test file: covered by existing suites (40 pipeline/export/durability
  tests re-run green) plus the browser checks below.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Edit → close → restart → reopen → export restores choices | draft restore (existing) + durable versions (new) | same choices restored | draft path unchanged + `edit_versions` now persisted server-side; full restart cycle requires a manual browser session | **PARTIAL — manual session NOT RUN** | code; unit suites green |
| Output matches preview (overlays) | canvas maps export coords → preview box | same position | letterbox-aware mapping implemented; visual comparison needs a browser session | **PARTIAL — NOT RUN visually** | drawOverlays code |
| Text punctuation/Unicode correct | canvas `fillText` (no shell-escaping path in preview); export path uses drawtext escaping (task 06) | correct rendering | preview uses canvas text (Unicode-safe by construction); export escaping covered by task 06 tests | PASS (preview by construction; export via task 06) | code + task 06 tests |
| Undo/redo + keyboard focus | pre-existing implementation | works | retained; regression suites green | PASS (unchanged) | existing tests |
| Malformed/stale drafts recover | `loadEditorDraft` clamps + try/catch | no crash, valid project preserved | unchanged behavior | PASS | code |
| No unrouted React editor opens | route inventory | none | no routes added to React app; editor lives only in /app | PASS | route inventory |
| API response/types match runtime | tsc on website unaffected; backend py_compile | clean | compile OK; 40 pipeline/export/durability tests green | PASS | command output |

## Migration and rollback

R03 remediation (2026-09-18) moved `edit_versions` into SQLite schema v4;
`job.json` is now a derived snapshot. The one-time migration imports legacy
edit history from snapshots into existing SQLite jobs. Old jobs without the
field read as `[]`. Downgrading binaries after migration is not validated.

## Remaining blockers

- Manual/automated browser session for the visual restart-export cycle and
  overlay-position comparison (ACCEPTANCE gate 18's full parity run).
- React workspace inventory (step 5) intentionally deferred with the task 01
  "one shipping UI" decision; document retirement or completion as follow-up.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
