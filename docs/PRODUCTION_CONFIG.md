# CLPZ — Configuration & Environment Reference

Every setting is an environment variable with a safe default in
`backend/config.py` / `backend/main.py`. **No secrets are committed to Git.**

## Configuration classes

| Var | Used in | Default | Class |
|---|---|---|---|
| `CLPZ_DEBUG` | web prod | `1` (dev) | **Set `0` in production.** Disables dev backdoors: resets endpoint, dev verification codes in responses, loose rate limits (1000/min → 10/min auth, 5/min forge), cookie `Secure` flag turns on |
| `CLIPFORGE_DATA` | all | `backend/data` | local state dir (SQLite DB + job folders) |
| `CLIPFORGE_CLIPS_DIR` | desktop | `~/Videos/CLPZ Clips` | where "Save" copies finished clips |
| `CLIPFORGE_AUTO_CLEANUP_HOURS` | all | via jobs cleanup | temp/job retention |
| `CLPZ_ADMIN_EMAIL` | all | *(empty)* | **secret-ish:** the account with this email gets admin. Required for admin functions |
| `CLPZ_ALLOWED_ORIGINS` | web prod | `http://localhost:8000,…` | CORS allowlist — **must be set to the real domain in production** |
| `RESEND_API_KEY` | web prod | *(empty)* | email delivery for verification/reset. Without it, email is skipped (debug mode returns codes in responses; production must have the key) |
| `CLPZ_FROM_EMAIL` | web prod | *(empty)* | Resend sender address |
| `NEXT_PUBLIC_SUPABASE_URL` | web prod | *(empty)* | Supabase project URL. Set + service key ⇒ auth/credits switch to Supabase mode |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | web prod | *(empty)* | anon key (safe for client) |
| `SUPABASE_SERVICE_ROLE_KEY` | web prod | *(empty)* | **SECRET — server only, never in frontend, never in Git** |
| `YT_COOKIES_FILE` | desktop | `backend/cookies.txt` | optional YouTube cookies (secret — never commit) |
| `YT_BROWSER_COOKIES` | desktop | *(empty)* | browser name for cookie extraction |
| `WHISPER_MODEL` | all | `tiny` | model size (benchmark before changing) |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE` / `WHISPER_TASK` | all | `auto`/`auto`/`transcribe` | transcription tuning |
| `MAX_CONCURRENT_JOBS` | all | `1` | keep 1 on 8 GB machines unless measured |
| `MAX_CLIPS_DEFAULT` | all | `5` | default clips per forge |
| `CLIP_MIN_SECONDS` / `CLIP_MAX_SECONDS` | all | `15` / `60` | clip length bounds |
| `COST_PER_FORGE` | all | `1` | credits per forge |
| `CLIP_LAYOUT`, `FACECAM_MAX_FACE_FRAC`, `SPLIT_FACE_HEIGHT`, `CAPTION_*`, `LOUDNORM`, `RENDER_WORKERS`, `BLACK_BAR_HEIGHT` | all | tuned defaults | rendering knobs — do not change without A/B comparison |

## Per-environment requirements

### Development (this machine)
`CLPZ_DEBUG=1` (default) — loose limits, dev codes in responses, HTTP cookies. Never expose to the internet.

AWS/Bedrock/boto3: fully removed from the codebase and excluded from packages (verified by the build audit). CLPZ has zero AWS dependencies.

### Desktop (CLPZ.bat / PyWebView)
Runs on `127.0.0.1` — not reachable from the network. Debug defaults are acceptable. Optional: cookies for YouTube bot-checks.

### Production web (Vercel/server)
Required, or do not deploy:
1. `CLPZ_DEBUG=0`
2. `CLPZ_ALLOWED_ORIGINS=https://<your-domain>`
3. `RESEND_API_KEY` + `CLPZ_FROM_EMAIL` (verification/reset emails)
4. `CLPZ_ADMIN_EMAIL=<owner account>`
5. Persistent storage for `CLIPFORGE_DATA` (or activate Supabase below)
6. Supabase (when activated): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — service key **server-side only**

With `CLPZ_DEBUG=0`: the `/api/jobs/reset` test endpoint returns 404, rate limits drop to production values (10/min auth, 5/min forge per IP), session cookies get `Secure`, and password-reset/verification codes are never returned in API responses.

## Secrets inventory (what must never appear in Git or frontend bundles)
`SUPABASE_SERVICE_ROLE_KEY` · `RESEND_API_KEY` · `YT_COOKIES_FILE` contents · session tokens · password hashes.
Verified: frontend build (`frontend-app/dist/assets/*.js`) contains none of these (scanned).
