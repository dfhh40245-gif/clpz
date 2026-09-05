# CLPZ — Android Architecture & Mobile Strategy (Chunk 16)

Status: **ARCHITECTURE DEFINED — implementation deliberately deferred.**
This document is the contract for building Android later without redesign.
It contains no implementation and introduces no paid infrastructure.

---

## 1. Current architecture (inspected)

```
WEBSITE (React SPA, served at /new/* by FastAPI; Vercel-ready)
  landing · auth · done page
        │ same FastAPI backend
        ▼
backend/main.py  ──►  auth_provider.py    (local SQLite ⇄ Supabase, auto-switch)
        │             credits_provider.py (local SQLite ⇄ Supabase, auto-switch)
        │             jobs.py             (job orchestration, data/<job_id>/)
        │             pipeline/           (yt-dlp → faster-whisper → analyzer → ffmpeg)
        ▼
SQLite (backend/data/clpz.db) — users, sessions, credits,
credit_transactions, jobs, verification_codes, idempotency_keys

DESKTOP (Windows)
  CLPZ.bat → run_desktop.py → desktop/app.py (PyWebView window)
  → backend on 127.0.0.1:<port> → /app?desktop=1 (legacy HTML workspace)
  Local processing: yt-dlp, faster-whisper (tiny, int8 CPU), ffmpeg, face tracking
```

Key facts that shape Android:

- **Provider pattern already exists.** `auth_provider`/`credits_provider`
  transparently use Supabase when `NEXT_PUBLIC_SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY` are set, else local SQLite. One codebase can
  serve both a Vercel website backend and this dev backend.
- **Sessions are server-side** opaque tokens (SQLite `sessions` table, httpOnly
  cookie for web; `auth_token` field also accepted by `/api/jobs`).
- **Credits are server-authoritative** with idempotency keys and an auditable
  transaction ledger. Nothing client-side is trusted.
- **Jobs hold large local files** (`data/<job_id>/`): source video, SRT,
  words.json, rendered MP4s. These are local-by-design and never uploaded.
- **Desktop is login-optional in practice:** the PyWebView window opens the
  workspace directly; auth/credits hooks exist but the desktop flow does not
  gate on them.

---

## 2. Android's role (defined)

**Android is a companion client to a CLPZ account — not a shrunken desktop app
and not a processing node.**

In scope:

- Login / signup (same CLPZ identity as website)
- Import: pick a video from the gallery, or paste a YouTube URL
- Choose options (clip count)
- Forge → monitor job progress
- Receive generated clips when ready
- Preview clips (9:16, vertical player)
- Light finishing: trim start/end, caption on/off/position, re-render
- Save to device / native share sheet (TikTok, Shorts, Reels targets)

Out of scope for Android:

- Running the transcription/analysis/render pipeline on-device
- Admin functions
- Account/billing management beyond viewing balance
- Being the primary product — desktop remains the full workspace

**The two supported topologies (both keep heavy processing off the phone):**

1. **Local-network pairing (recommended first):** the Android app talks to the
   user's own desktop CLPZ backend over the LAN (`http://<desktop-ip>:8000`).
   Jobs run on the desktop GPU/CPU; the phone is a remote control + viewer.
   Zero cloud cost, zero privacy exposure — video never leaves the user's
   machines.
2. **Cloud account mode (later, optional):** Android talks to the same FastAPI
   backend deployed centrally (Vercel-compatible deployment with Supabase
   mode). Processing still cannot happen on Vercel for video of this size, so
   cloud mode at first offers account/credits/job-history sync and clip
   delivery only for jobs created from a paired desktop — or a future
   self-hosted worker. No per-video cloud AI is introduced.

This preserves the cost principle: **the customer's hardware does the expensive
work** in both topologies.

---

## 3. Local vs on-device processing analysis (Step 3)

| Factor | A: on-device Android pipeline | B: Android as client (desktop/companion does pipeline) |
|---|---|---|
| CPU | Mid phones: 15–40 min per 10-min video (whisper tiny int8 + x264 software encode runs hot) | Phone: near-zero. Desktop: proven pipeline |
| RAM | faster-whisper tiny ≈ 500 MB–1 GB + decode buffers; kills background apps; many targets have 4–6 GB | Phone needs only streaming/playback RAM |
| Battery | 30–60% drain per job; thermal throttling extends runs | Negligible |
| Storage | Source + temp + outputs ≈ 2–4 GB per job | Phone stores only final clips (~10–40 MB each) |
| FFmpeg | Available (ffmpeg-kit), but encode speed on mobile SoCs is poor without hwencode-specific tuning; caption burn-in via libass is slow | Desktop ffmpeg already validated |
| faster-whisper | Runs via ONNX/CTranslate2 ports, but Android support is community-maintained and fragile | Not needed on phone |
| Face tracking | OpenCV on mobile OK for preview, slow for full analysis | Desktop already does it |
| Network | None (full offline possible) | LAN or internet to reach job API |
| Cost | $0 infra, but poor UX | $0 infra |
| Scalability | Per-user hardware absorbs load | Per-user hardware absorbs load |
| Privacy | Best possible | Video stays on user's own machines (LAN mode) |

**Recommendation: B.** On-device full pipeline fails the UX bar (30+ min,
hot phone, dead battery) for the first Android release. Revisit on-device
inference only when/if a lightweight "auto-captions only" mode is proven
valuable (whisper tiny + template captions is the plausible future subset).

---

## 4. API boundary (Step 4)

### Already exists and is reusable as-is (mobile-ready)

| Purpose | Endpoint | Notes |
|---|---|---|
| Signup / login / logout | `POST /api/auth/signup`, `/login`, `/logout` | Login returns a session token; cookie + token both work |
| Session check | `GET /api/auth/me` | Cheap heartbeat |
| Email verification | `POST /api/auth/request-verification`, `/verify-email` | |
| Password reset | `POST /api/auth/forgot-password`, `/reset-with-code` | |
| Credit balance | `GET /api/credits/balance` | Server-authoritative |
| Credit ledger | `GET /api/credits/transactions` | |
| Create YouTube job | `POST /api/jobs` | Accepts `auth_token` (good for mobile: no cookie jar needed) |
| Create upload job | `POST /api/jobs/upload` | Multipart; phone gallery videos work today |
| Job list / status | `GET /api/jobs`, `GET /api/jobs/{id}` | Polling is sufficient (no websockets needed) |
| Cancel / retry | `POST /api/jobs/{id}/cancel`, `/retry` | |
| Clip metadata | inside job JSON (`clips[]`) | Includes thumbnail path, duration, text |
| Clip media | `GET /api/jobs/{id}/clips/{i}/stream`, `/thumbnail` | Range-capable stream = mobile playback ready |
| Clip download | same stream endpoint (Content-Disposition) | |
| Editor save/re-render | `POST /api/jobs/{id}/clips/{i}/save`, `/edit` | Mobile "finish" screen reuses this |

### Gaps to add later (small, no redesign)

1. **`GET /api/mobile/config`** — returns pairing info, min app version,
   feature flags. (New, trivial.)
2. **Desktop pairing**: a pairing code shown in the desktop app
   (`POST /api/pair/start` → 6-digit code; phone posts it; backend binds the
   phone's account to this desktop for LAN job submission). Needs LAN
   discovery (mDNS or manual IP entry) + one shared secret. (New, medium.)
3. **Push-lite job completion**: polling is fine for v1; optional
   `GET /api/jobs?since=` delta endpoint to save battery. (New, trivial.)
4. **Supabase mode hardening for public deployment** — rate limits per IP+
   account on auth endpoints when the API is internet-facing. (Exists locally;
   revisit at deployment time.)

No existing endpoint needs to change shape for Android v1.

---

## 5. Authentication (Step 5)

- One identity: **CLPZ account** in `users` (SQLite today, Supabase Auth when
  configured). Android logs into the *same* backend — no separate mobile user
  store, no duplicate accounts.
- **Token handling on Android:** store the session token in the Android
  **Keystore-backed EncryptedSharedPreferences**. Never in plain prefs, never
  logged. Send as `Authorization: Bearer <token>` (backend already accepts
  `auth_token` in job creation; add the same acceptance to remaining
  user-scoped endpoints when building Android — small change).
- Session lifetime: server-side opaque token with expiry in the `sessions`
  table (already exists); logout destroys server-side (already exists).
- **Google OAuth (Android):** when Supabase mode is active, use Supabase
  Auth's Google provider with the native Android sign-in (Google Identity
  Services). The backend's Supabase path already validates Supabase tokens —
  Android's Supabase JWT slots into the same `validate_session` flow. Until
  Supabase is configured, Android ships with email/password only (matches the
  website's current live capability — no fake parity).
- **Never on the phone:** service-role keys, Supabase service key, cookies.txt,
  admin endpoints. Android uses anon-level access only; all authority stays
  server-side.
- Website/browser login flow stays exactly as today (`/new/auth` → done page);
  Android's login screen mirrors it visually but is native.

## 6. Credits (Step 6)

- Same server-authoritative ledger (`credit_transactions`, idempotency keys).
  Android sends an `idempotency_key` on job creation (the API already
  generates one server-side if omitted — double-tap/retry safe today).
- The phone displays balance read-only from `/api/credits/balance`. It can
  never compute, cache-authoritatively, or refund credits. Refund-on-failure
  stays a server-side pipeline concern.
- Free trial (10 credits) unchanged — server-side flag, not device-bound.
- No payments in this chunk. When payments exist, Android buys credits via a
  web-view/redirect to the website's checkout (Play Billing only if/when
  distribution requires it — documented decision, not implemented).

## 7. Mobile UX (Step 7)

Flow (each step a native screen):

```
Login ──► Home (balance chip, job list)
   │
   ├─ Import: [YouTube URL] or [Pick from gallery]
   ├─ Options: clip count (1–5), caption style preset
   ├─ Forge ──► Processing screen (progress, cancel)
   ├─ Clips grid (9:16 thumbnails, status badges)
   ├─ Clip preview (vertical player, captions visible)
   ├─ Finish (mobile-scoped editor):
   │     • trim start/end (two handles)
   │     • captions on/off, position (low/mid/high)
   │     • re-render → replaces preview
   └─ Export: [Save to gallery] [Share…]
```

Editor scope on phone: **trim + caption position + re-render only.** No
timeline, no multi-clip editing, no layout surgery. Everything else stays a
desktop strength. Re-render uses the existing `/edit` endpoint.

## 8. Sharing / export (Step 8)

- Save: MediaStore download to `Movies/CLPZ/` — appears in Gallery.
- Share: Android `Intent.createChooser` / `ShareSheet` with the rendered MP4 —
  direct targets: TikTok, Instagram Reels, YouTube Shorts.
- No cloud storage introduced. Files live on the desktop until the phone
  downloads them; the phone's copy is the user's to keep or delete.
- Desktop keeps `data/` cleanup policy (24h) — phone downloading a clip is the
  natural "archive" step before cleanup.

## 9. Offline behavior (Step 9)

| Capability | Offline? |
|---|---|
| Browse previously downloaded clips | ✅ (local MediaStore/ app storage) |
| Light trim/export of downloaded clips | ✅ (local ffmpeg-kit trim, no captions change) |
| Cached account/balance view | ✅ (last-known, clearly stale-labeled) |
| New Forge / job status | ❌ requires desktop or cloud reachable |
| Caption re-render | ❌ requires the pipeline host |

Never promise offline Forge. The document-level commitment: offline = library
+ basic trim only.

## 10. Technology decision (Step 10)

| Option | Performance | Media access | Fit with existing stack | Maintainability | Verdict |
|---|---|---|---|---|---|
| Native Kotlin + Jetpack Compose | Best (playback, share, keystore) | Best (MediaStore, ExoPlayer, SAF) | API-first, no sharing needed | Single new codebase to maintain | **Selected** |
| Flutter | Good | Good (plugins) | New stack, Dart | Good | Strong second |
| React Native | Good | Good | Would reuse React skills/TS types | Metro/bridges churn | Viable |
| WebView wrapper of `/new` | Poor (player/share/keystore all fight the wrapper) | Poor | Trivial | Fragile | Rejected |

**Selected: native Kotlin + Jetpack Compose.**
Rationale: the app is thin (API + player + share + trim). Native gives
ExoPlayer (best-in-class vertical video playback), MediaStore/share-sheet and
Keystore without bridges, and Play-store-grade distribution. The shared
contract with the rest of CLPZ is the REST API + this document, not shared
code — so no framework is pressured to span desktop/web/mobile. TypeScript
types for the API already exist in `frontend-app/src/lib/api.ts` and translate
mechanically to Kotlin data classes.

Cost: Kotlin toolchain is free; building locally requires only the Android SDK
($0). No paid CI required (GitHub Actions free tier covers a small project).

## 11. Explicitly NOT built in this chunk

- No Android project scaffold (by instruction)
- No pairing endpoint implementation (design only)
- No Supabase activation (still blocked on credentials — Chunk 13 blocker)
- No payments, no Play Billing

## 12. Cost check (Step 12)

| Item | Cost |
|---|---|
| Android app (Kotlin, local dev) | $0 |
| LAN pairing (phone ⇄ desktop) | $0 — no servers |
| Job processing | $0 — user hardware |
| Push notifications | none (polling) → $0 |
| Cloud mode (later, optional) | only existing backend hosting cost; no GPU, no per-video AI |
| Recurring infrastructure introduced | **$0/month** |

## 13. Risks / notes

- **LAN pairing security:** pairing code exchange must be short-lived and the
  phone must re-verify the desktop's token on each session; job submission on
  LAN should require the paired token (not open endpoints). To be designed
  carefully at implementation time (rate-limit + bind to account).
- **Battery-friendly polling:** poll at 2s while a job is active, back off to
  30s idle; add `?since=` delta later if needed.
- **Large uploads from phone (gallery videos):** existing `/api/jobs/upload`
  works, but LAN upload of 1–2 GB needs chunked/multipart progress UI. Not an
  API change; a client concern.

---

## VERDICT

Android can be added later as a **thin native Kotlin client** against the
**existing API**, using the **existing identity/credit provider architecture**,
with **all processing on the user's desktop (LAN pairing) or a later
cloud-account mode** — **no new recurring infrastructure**, **no redesign of
desktop or web**. Implementation can start from this contract whenever
priorities allow.
