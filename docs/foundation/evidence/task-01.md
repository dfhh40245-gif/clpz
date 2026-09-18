# Task 01 — Define one product and architecture contract

Task: 01 (product contract)
Commit: 76e4b0a (baseline; task 01 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64), user `RepairTest`
Runtime/tool/model versions: Python 3.12.14 (project `.venv`), FFmpeg 9.0.1 essentials (bundled), Node/npm **not installed** on this machine

## Scope and policy decisions

Adopted the conservative baseline already stated in the owner-provided
foundation docs: free Windows local release first (vanilla `/app` UI), Next.js
public site, Supabase for cloud identity/business data, Android as labeled
preview, no hosted media processing. All still-open commercial choices are
recorded as OPEN in `docs/foundation/DECISIONS.md` — none were invented.
`probe_current.py` and the audit state were treated as evidence, not as
authorization to change application behavior in this task (task 01 is
documentation/contract only).

## Original reproduction

Not a code defect — the deliverable was the missing/incorrect contract:
- README claimed "There is no Supabase or other hosted service dependency",
  while `website/lib/supabase-*` and `supabase/migrations/0001_initial_schema.sql`
  exist and mobile-android uses Supabase auth (finding F28).
- The supplied diagram put the analyzer before transcription and omitted the
  packaged launcher and website/cloud paths (verified against
  `backend/jobs.py::_run_pipeline` and `desktop/frozen_launcher.py`).

## Files changed

- `docs/ADR-0001-product-architecture.md` (new): ADR-0001..0006 with status,
  context, decision, consequences (product scope, UI, store ownership, real
  pipeline order + entry paths, local API boundary, account model).
- `docs/ARCHITECTURE.md` (new): corrected Mermaid diagram (transcription before
  analysis; frozen launcher dotted edge; website/Supabase/Android paths),
  route/data ownership table, trust boundaries, dev-vs-installed paths,
  capabilities matrix (works / broken / untested).
- `docs/foundation/DECISIONS.md` (new): owner decision register D1–D12 with
  status and the tasks each decision blocks.
- `README.md` (edited): corrected architecture notes (Supabase exists for
  website/Android; media stays local), repository layout now names the
  shipping UI, website, Android, supabase, and foundation docs; labeled
  `CLPZ_ADMIN_EMAIL` bootstrap as known defect F01 instead of a feature.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Every diagram box maps to an existing file or an explicitly proposed component | manual walk of `docs/ARCHITECTURE.md` diagram against repo | all boxes map to files | verified: run_desktop.py, desktop/app.py, desktop/server.py, backend/main.py, desktop/frozen_launcher.py, backend/clpz_server.py, frontend/clpz.html, frontend-app, backend/jobs.py, pipeline/*.py, cutter, website/, Supabase, mobile-android, frontend/ legacy | PASS | docs/ARCHITECTURE.md |
| The document names one shipping desktop UI and one authoritative store per data category | read ADR-0002 + ADR-0003 ownership table | single UI + per-category authority | vanilla `/app` named; per-category authority table present (jobs→SQLite, identity/paid→Supabase, media→local FS, Android→on-device) | PASS | docs/ADR-0001-product-architecture.md |
| A new contributor can locate all three products and distinguish local anonymous use from cloud account access | read README layout + ARCHITECTURE surfaces | three products locatable; local vs cloud distinction explicit | desktop (`desktop/` + `/app`), website (`website/`), Android (`mobile-android/`); local anonymous workflow vs Supabase identity distinguished in README + ADR-0001 §3 | PASS | README.md, docs/ARCHITECTURE.md |
| All unresolved business choices have an owner and identify which later tasks they block | read DECISIONS.md register | every open choice recorded with blockers | D1–D12 recorded; OPEN entries name tasks 14/15/16/21 and scope tasks | PASS | docs/foundation/DECISIONS.md |

## Migration and rollback

No code or stored data touched; rollback = revert the four files above.

## Remaining blockers

- D2/D3/D5/D6/D7 (commercial terms) are owner decisions and remain OPEN by
  design; they block tasks 14–16 completion claims but not their fixture work.
- Node.js/npm are not installed on this machine, so no JS-side verification
  applies to this task (none required).

## Next unblocked task

Task 02 (reproducible development).
