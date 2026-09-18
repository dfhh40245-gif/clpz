# Run and verify the project

All commands below are **PowerShell** unless labeled otherwise. Paths assume the terminal starts at the repository root. Close test servers before repeating tests. Use synthetic or consented fixtures, never customer databases.

These commands describe the current project, including its missing dependencies. Task 02 replaces the temporary extra-package install with committed complete manifests and deterministic locks.

## Prerequisites

- Windows development machine, Git and Python 3.12.
- A supported Node.js installation including npm; use the version selected/tested in task 02. Current React manifest requires Node >=22; current CI selects Node 22.
- Enough disk for Python/native packages, local media and models. The pipeline itself rejects less than 2 GiB free; that is not a guarantee of sufficient space for every input.
- Working ffmpeg/ffprobe. Bundled tools are under backend/bin; execute them to verify, not just check existence.
- Desktop GUI: requirements_desktop.txt plus a working PyWebView Windows runtime.
- Installer: PyInstaller and Inno Setup. Android: Android Studio/SDK, JDK 17 and the project-compatible Gradle toolchain.
- Cloud tests: a separate development/staging Supabase project and provider sandbox/test flow. Never put service-role/payment secrets in desktop/mobile/browser bundles.

## Current local setup

```powershell
Set-Location 'C:\Users\RepairTest\Desktop\clpz-actual'
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
& .\.venv\Scripts\python.exe -m pip install python-multipart pytest requests httpx
& .\.venv\Scripts\python.exe -m pip check
npm --prefix frontend-app ci
npm --prefix website ci
```

Change only the first path if someone else cloned elsewhere. If py is unavailable, use the full path to an installed Python 3.12 executable to create the venv. Activation is optional because these commands use the explicit interpreter.

The audit machine had no npm on PATH and used the already-installed node_modules directly for builds/tests. Therefore the audit's passing JavaScript builds **do not prove a clean npm ci**.

## Backend baseline

```powershell
$auditDir = Join-Path ([System.IO.Path]::GetTempPath()) ('clpz-check-' + [guid]::NewGuid().ToString('N'))
$env:CLIPFORGE_DATA = $auditDir
$env:CLIPFORGE_CLIPS_DIR = Join-Path $auditDir 'exports'
$env:CLPZ_DISABLE_MAINTENANCE = '1'
Push-Location backend
try {
    & ..\.venv\Scripts\python.exe -m pytest tests -m 'not slow' -q --tb=short
} finally {
    Pop-Location
}
```

Current test fixtures also start servers with their own backend/test_data directory and fixed ports. Do not run multiple copies simultaneously; task 02 must remove that collision risk. The marker “not slow” does not guarantee no network-triggered background jobs.

Recorded result: **110 passed, 2 failed, 1 skipped, 9 deselected**. Failures: insufficient-credit expectation (200 vs 402) and bundled yt-dlp --version. The credit test failed again alone. Do not label the suite green or suppress these failures.

## Targeted audit probes

```powershell
& .\.venv\Scripts\python.exe docs/foundation/probe_current.py
```

Reads application code, creates temporary fake accounts and generated media, records current defects in evidence/current-probes.json. It does not implement fixes. An exit code of zero means probes completed, **not** that the application is correct. Each result must be interpreted against AUDIT.md. Temporary test media is retained at the reported path.

## Frontend checks

```powershell
npm --prefix frontend-app run build
npm --prefix frontend-app test
npm --prefix frontend-app run lint
npm --prefix website run build
npm --prefix website run lint
```

Each exit code must be checked independently; PowerShell does not automatically stop on every nonzero native command. Current website build can read website/.env.local automatically. Use staging/test values, and do not print or commit them. Build success does not test live signup, OAuth or payments.

Current results: React build and 3 tests pass; React lint reports 9 warnings. Website build and lint pass. No website automated flow tests are declared in its current package scripts.

## Start local workspace for a manual smoke test

In a new terminal, from the root:

```powershell
$env:CLIPFORGE_DATA = Join-Path ([System.IO.Path]::GetTempPath()) ('clpz-smoke-' + [guid]::NewGuid().ToString('N'))
$env:CLIPFORGE_CLIPS_DIR = Join-Path $env:CLIPFORGE_DATA 'exports'
$env:CLPZ_DEBUG = '0'
& .\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/app?desktop=1. Import a local speech clip. Expected workflow after repairs: inspect progress, play generated clip, edit, export, close/restart and reopen it. Use the **same** temporary data path to verify restart; generating a new path creates an empty workspace.

For the native dev window, install requirements_desktop.txt and run run_desktop.py. Its current development launcher chooses desktop_data itself, so use a disposable checkout if testing lifecycle/data behavior. Native GUI/installed EXE was not exercised in this audit.

Website: npm --prefix website run dev, then open its reported URL. Configure only development/staging values using website/.env.example; provider configuration is needed for actual account flows.

## Installer and Android

Do not treat python packaging/build_windows.py as a verified one-command installer yet. It currently assembles a folder, with the gaps in task 13. Follow tasks 12/13 before release acceptance.

Android currently relies on Android Studio or workflow-installed Gradle; no checked-in Gradle wrapper was found in tracked files. Read mobile-android/README.md, then task 20. This audit did not compile or run an Android device.

## Troubleshooting without hiding failures

| Symptom | Meaning/action |
|---|---|
| python opens the Windows Store | Use an installed interpreter's absolute path. |
| npm not found | Install/use Node with npm; do not infer npm availability from node --version. |
| FastAPI requests python-multipart | Missing current manifest entry; temporary setup above supplies it; task 02 fixes the manifest. |
| A test port is occupied | Stop only your own test process or isolate the fixture; never reuse an unknown server. |
| yt-dlp.exe --version exits 1 | Known audit failure; Python module works here, but downloader chooses bundled executable first. Task 13 must fix delivery. |
| Insufficient-credit test gets 200 | Investigate worker/refund timing and test isolation; do not remove refund logic to force 402. |
| Mute/0.25 export gives 500 | Reproduced defects; use task 06. |
| Build succeeds but login fails | Provider settings/runtime verification are separate; use tasks 14/16/17. |
| Installed app cannot find server | Package-path mismatch; task 12. |
| Second backup fails | Nonunique destination; task 10. |

