# CLPZ Architecture Decision Record

Status: Adopted as the implementation baseline for the 22-task foundation plan
(docs/foundation/). Supersedes the "Architecture notes" in the root README and
the doc claims it corrected. **Existing code wins over this record only where a
code-vs-doc disagreement was explicitly accepted here; the audit (AUDIT.md)
lists the remaining code-level defects.**

Decisions are listed newest-last inside each ID so later amendments stay
append-only. Owner decisions still open are tracked in
[docs/foundation/DECISIONS.md](foundation/DECISIONS.md) — this record never
invents commercial terms.

## ADR-0001 — First stable product is the Windows local workspace

**Status:** Adopted (task 01, 2026-09-17).

**Context:** The repository contains a Windows PyWebView/FastAPI local video
processor, a vanilla HTML desktop workspace at `/app`, a partially routed React
workspace at `/new`, a Next.js public website, a Supabase cloud schema and a
native Android editor. Resources cannot finish all surfaces at once, and the
founder asked for a conservative baseline.

**Decision:**

1. The **first release** is the Windows desktop app using the existing vanilla
   `/app` workspace. Cloud billing and Android are explicitly **out of scope
   and disabled/labeled** in that release, per the ACCEPTANCE.md release rule.
2. The **public website** is the Next.js app in `website/` (marketing, auth,
   account, download). The legacy static `frontend/` pages and the React
   `/new` surface are kept working in development but are not release surfaces;
   task 18 inventories the React login/animation leftovers.
3. **Supabase owns cloud identity and business data** (accounts, payments,
   entitlements) for website/Android. The desktop's local SQLite accounts and
   credits remain **development/legacy** state: local credit edits must never
   be able to mint cloud entitlements (tasks 08, 16).
4. **Android stays a separately labeled preview.** It imports/exports
   on-device, uses Supabase auth, and has **no implemented connection to the
   local FastAPI backend**; do not assume or advertise one.
5. **No hosted video processing.** Download, transcription, rendering and
   editing run on the user's machine. Introducing cloud media upload requires
   an explicit new ADR.

**Consequences:** Paid/credit features in the desktop UI are labeled as legacy
or disabled until tasks 14–16 land; the website checkout stays behind a
fail-closed gate until task 15 acceptance; hosted-workspace features are not
built on the media backend.

## ADR-0002 — Desktop UI stays vanilla /app for the first release

**Status:** Adopted (task 01).

**Context:** `frontend/clpz.html` (vanilla) is the workspace that actually
ships in the installed build and has working drafts, speed/mute/trim preview
and keyboard controls. The Vite React app routes only landing/auth/done and has
unrouted editor components.

**Decision:** Keep the vanilla `/app` workspace as the single shipping desktop
UI. The React editor is not routed and receives no duplicate features. React
migration (if ever) is separate future work with its own ADR; until then
`frontend-app` remains a `/new` landing/auth surface only.

**Consequences:** Editor work (task 18) happens in `frontend/clpz.html` plus
backend versioned edit APIs. The React login/reset/Google leftovers must be
either connected or removed through the documented migration in task 18 — not
silently kept as a second account system.

## ADR-0003 — One authoritative store per data category

**Status:** Adopted (task 01; enforced by tasks 05, 08, 09, 10).

**Context:** Jobs are written to both SQLite and `job.json`; startup recovery
reads JSON snapshots. Payments/credits exist locally (SQLite) *and* in the
Supabase schema. Two writers for one fact have already produced divergent
state.

**Decision (ownership contract):**

| Data/capability | Authority | Local copy | Rule |
|---|---|---|---|
| Original videos, audio, transcripts, rendered outputs | Local filesystem project store | Yes | Never upload media to cloud by accident |
| Jobs, attempts, project/edit versions | Local transactional store (SQLite, task 10) | `job.json` is a derived snapshot | One authority; committed state survives restart |
| Cloud user identity | Supabase Auth | Secure minimal session cache | A typed email is never a verified identity |
| Purchases, entitlements, cloud credits | Cloud service/database (Supabase) | Minimal verified cache | Local SQLite edits cannot grant cloud access |
| Local anonymous workflow | Explicit desktop runtime | Per-launch capability/workspace | No public hosted workspace implied |
| Release version/artifact hash | Tested release manifest | Cached metadata | Download points to the exact tested artifact |
| Android projects | On-device store | Yes | Separate product surface, not parity by assumption |

**Consequences:** Task 10 declares SQLite the job authority with JSON as a
derived snapshot and migrates existing installations; task 08/09 scope the
local ledger as development/legacy accounting; task 14 owns the cloud side.

## ADR-0004 — Real pipeline order and the packaged entry path

**Status:** Adopted (task 01; corrects the supplied diagram and README).

**Decision (current behavior, verified in code):**

- Pipeline order in `backend/jobs.py::_run_pipeline`:
  **intake (download/upload) → transcription (`pipeline/transcriber.py`) →
  parse (`pipeline/srt_parser.py`) → candidate analysis (`pipeline/analyzer.py`)
  → layout plan (`pipeline/cutter.plan_layout`) → captions
  (`pipeline/captions.py`) → render (`cutter.render_clip` → FFmpeg).**
  Analyzer does *not* precede transcription.
- Entry points: development `run_desktop.py → desktop/app.py →
  desktop/server.py`; installed `desktop/frozen_launcher.py →
  backend/clpz_server.py`. The installed assembly puts the server at
  `clpz_server/clpz_server.exe`; the launcher's path mismatch is finding F14.
- The desktop window opens `/app` served by `frontend/clpz.html`. The React
  router covers only `/new` landing/auth/done.
- Website checkout (`/api/gumroad/ping`) records payment rows only; it does not
  link accounts or grant entitlements (finding F18, task 15).

**Consequences:** Documentation and the Mermaid diagram in
[docs/ARCHITECTURE.md](ARCHITECTURE.md) describe this corrected topology;
acceptance (task 22) tests the installed path, not just dev.

## ADR-0005 — Local API boundary and capability model

**Status:** Adopted (task 01; implemented by task 03).

**Decision:** The desktop backend is a **local-only** service: loopback bind,
Host/Origin validation, and a per-launch capability token delivered only to the
intended UI. Anonymous local jobs keep working, but every state-changing route
must pass the capability check. The media backend must never silently become a
hosted multi-tenant service; enabling remote exposure requires a new ADR and
the production-mode checks of task 03.

**Consequences:** `CLPZ_DEBUG` alone no longer authorizes anything; production
startup rejects unsupported insecure modes (task 03 acceptance).

## ADR-0006 — Account model until shared identity ships

**Status:** Adopted (task 01; implemented by task 04).

**Decision:** Admin rights come from a **provisioned immutable identity**
(trusted local maintenance command), never from matching `CLPZ_ADMIN_EMAIL`
against an unverified registration. Password hashing is versioned with a
migration-on-success path. The website/Android Supabase identity remains the
only cloud identity; desktop SQLite accounts are local-only until task 16
implements the secure handoff.

**Consequences:** Existing installs migrate via the documented provisioning
command; `CLPZ_ADMIN_EMAIL` matching is removed as an authorization mechanism.
