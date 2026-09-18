# Task 13 — Produce verified Windows installers and media tools

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + addition.
Priority: P1 release blocker.
Prerequisites: task 02, task 12.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The bundled yt-dlp executable exits 1 on --version, while python -m yt_dlp works in the audit venv. The build does not rebuild React or invoke Inno Setup, passes --specpath with existing specs, and package audit can report clean on an absent/empty output.

## Inspect these files

- packaging/build_windows.py
- packaging/clpz_server.spec
- packaging/clpz_launcher.spec
- packaging/clpz_installer.iss
- packaging/RELEASE_SHA256.txt
- backend/bin/yt-dlp.exe
- backend/pipeline/downloader.py
- docs/RELEASE.md

## Implementation steps

1. Diagnose the bundled downloader on a clean Windows machine; use a verified supported standalone artifact or a packaged module strategy, with provenance, checksum and version. Do not blindly replace binaries or depend on the developer's Python path.
2. Create one release command that builds required UI, freezes both executables using valid spec-mode options, assembles assets, bundles offline model/VAD files, and invokes Inno Setup.
3. Fail missing/empty package audits and missing binaries/models/fonts. Execute all bundled tools' version/smoke checks; do not accept file existence alone.
4. Centralize versioning; generate artifact hashes, dependency/native-tool notices and a release manifest. Separate assembly from signing/publishing and use explicit destinations. Document signing prerequisites without inventing certificates.

## Acceptance checks — all required for this task

- [ ] A clean build needs no stale dist or manually copied outputs and yields the documented installer filename.
- [ ] Package checks fail if output is missing or one required asset/tool fails.
- [ ] Install and process a local speech fixture offline on a machine with no Python; every bundled executable works.
- [ ] Install, upgrade and uninstall retain user projects according to the documented policy; release hashes correspond to the actual tested files.

## Deliverables and handoff

Reproducible release command, verified tool/model acquisition, installer, manifest, and clean-machine procedure.

Create or update docs/foundation/evidence/task-13.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

