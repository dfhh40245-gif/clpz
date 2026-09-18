# Bundled native binaries — provenance and update procedure

Task 13. Every binary under `backend/bin/` must have a known origin, a
recorded SHA-256, and a passing version smoke check. **File existence alone
is never acceptance evidence** (F15: the old yt-dlp.exe was a pip-script
launcher requiring `C:\Python314\python.exe` — it exited 1 silently on any
machine without that path).

## Current bundled set

| Binary | Kind | Version | SHA-256 | Source |
|---|---|---|---|---|
| `ffmpeg.exe` | standalone release build | see `ffmpeg -version` | record at build time | official ffmpeg release |
| `ffprobe.exe` | standalone release build | see `ffprobe -version` | record at build time | official ffmpeg release |
| `yt-dlp.exe` | official standalone release (PyInstaller onefile) | 2026.08.19 | `66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a` | github.com/yt-dlp/yt-dlp releases, verified against `SHA2-256SUMS` |
| `deno.exe` | standalone release build | `deno --version` | record at build time | official deno release |

## Why the old yt-dlp.exe failed

It was a pip-generated **entry-point launcher** (a PE stub containing the
zip-app `__main__.py` plus a baked shebang `#!C:\Python314\python.exe`).
Running it on a machine without Python 3.14 at that exact path exits 1 with
no output. The replacement is the official **standalone onefile build**,
which embeds its own runtime and needs nothing else.

Identification tip: `unzip -l yt-dlp.exe` listing only `__main__.py` plus a
`#!...python.exe` shebang inside the PE stub ⇒ pip launcher, NOT standalone.

## Fallback chain (backend/pipeline/downloader.py)

1. `backend/bin/yt-dlp.exe` — used only if `--version` smoke-checks at
   build/audit time (the packaged app's guaranteed-working path).
2. `python -m yt_dlp` inside the frozen server — the PyInstaller bundle
   includes the `yt_dlp` module, so the frozen app never depends on the
   developer machine's PATH.

## Update procedure

```powershell
# 1. Download the official standalone exe + checksum list
curl.exe -L -o yt-dlp.exe "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
curl.exe -L -o SHA2-256SUMS "https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS"

# 2. Verify the checksum EXACTLY matches the published list
Get-FileHash .\yt-dlp.exe -Algorithm SHA256
Select-String "^<hash>  yt-dlp.exe$" .\SHA2-256SUMS

# 3. Smoke-check
.\yt-dlp.exe --version

# 4. Copy into backend/bin/ and re-run the release build audit
Copy-Item .\yt-dlp.exe backend\bin\
python packaging\build_windows.py --audit-only
```

Never replace a bundled binary without a matching published checksum and a
passing smoke check.
