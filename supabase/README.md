# CLPZ — Supabase Setup Guide

The cloud layer holds **account/business data only**. The desktop app's
SQLite stays local; Whisper/FFmpeg/yt-dlp never move to the cloud.

## 1. Create / locate the project

1. Open https://supabase.com/dashboard
2. Check your organizations for an existing CLPZ project first — do not
   create duplicates.
3. If none exists: **New project** → name `clpz`, region closest to your
   users, set a strong database password (store it in a password manager,
   never in Git).

## 2. Apply the migrations (in order)

Apply **every** migration file in filename order — 0002 and 0003 are FORWARD
migration that upgrades databases which already applied 0001 (never edit
0001 to repair a deployed project):

1. `supabase/migrations/0001_initial_schema.sql`
2. `supabase/migrations/0002_cloud_foundation.sql`
3. `supabase/migrations/0003_cloud_device_identity.sql`

SQL Editor → paste each file's full contents → **Run** (0001 on a fresh
project; then 0002 on top of it).

Verify afterwards:

```sql
select tablename, rowsecurity from pg_tables
where schemaname = 'public';
```

Every user-scoped table must show `rowsecurity = true`. 0002 additionally
adds: key-scoped conflict-detecting `grant_credits` (concurrency-safe via
advisory lock + unique partial index), a `credit_buckets` table separating
expiring subscription credits from never-expiring purchased credits with a
defined spend order (`spend_credits`), subscription status constraints with
single-active-per-user enforcement and guarded transitions, and the
`profiles.full_name` column used by the website.

## 2b. Local role/concurrency tests (before deployment)

Run the harness against a DISPOSABLE local PostgreSQL only (never a
production project):

```bash
psql -v ON_ERROR_STOP=1 -f supabase/tests/local_role_tests.sql
```

It creates Supabase-equivalent roles, expects 0001 and 0002 to be applied, and asserts
RLS isolation (A cannot read B), blocked client writes, service-role-only
RPC execution, replay/conflict semantics, single-active subscriptions, and
the subscription-first spend order. All eight checks must print PASS.

After applying 0003 to the same disposable database, run
`psql -v ON_ERROR_STOP=1 -f supabase/tests/cloud_device_identity.sql`.
This checks one-use/expired/wrong-state exchanges and client role isolation.
These database-role checks remain **NOT RUN** until a disposable PostgreSQL or
staging Supabase database is available.

## 3. Authentication

Dashboard → Authentication:

- **Providers**: enable Email. Enable Google OAuth later once you add the
  Google client ID/secret (requires a configured OAuth consent screen).
- **URL Configuration**:
  - Site URL: your production URL (e.g. `https://clpz.vercel.app` or your
    custom domain)
  - Redirect URLs: add
    - `https://<production-url>/auth/callback`
    - `http://localhost:3000/auth/callback` (local dev)

## 4. API keys

Project Settings → API. Current naming:

- `Project URL` → `NEXT_PUBLIC_SUPABASE_URL` (safe for browser)
- `anon / publishable key` → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (safe for
  browser — RLS protects everything)
- `service_role / secret key` → **server only**. Used by the Gumroad
  webhook function. NEVER put this in `NEXT_PUBLIC_*` or client code.

## 5. Environment variables (Vercel)

Set in Vercel → Project → Settings → Environment Variables:

| Name | Scope | Value |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Production + Preview | Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production + Preview | anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Production + Preview | service key (server-only) |
| `GUMROAD_WEBHOOK_SECRET` | Production + Preview | from Gumroad webhook settings |
| `GUMROAD_PRODUCT_IDS` | Production + Preview | comma-separated product permalinks |
| `GUMROAD_DEFAULT_CREDITS` | Production + Preview | e.g. `100` |

After changing variables **redeploy** — existing builds keep old values.

## 6. What the desktop app does (and does not do)

The desktop app keeps its local SQLite database and media processing. For
cloud account linking, configure `CLPZ_ACCOUNT_URL` to the exact HTTPS origin
of the deployed website (HTTP is accepted only for localhost development).
The Windows app shows a state value; the signed-in website account page issues
a one-time code for that state. The desktop exchanges it over HTTPS and stores
the device token with Windows DPAPI. Cloud credits and entitlements are read
online from Supabase and are never copied into the local SQLite balance.
Paid usage/offline rules remain open in `docs/foundation/DECISIONS.md`.
