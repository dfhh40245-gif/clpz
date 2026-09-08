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

## 2. Apply the migration

SQL Editor → paste the full contents of
`supabase/migrations/0001_initial_schema.sql` → **Run**.

Verify afterwards:

```sql
select tablename, rowsecurity from pg_tables
where schemaname = 'public';
```

Every user-scoped table must show `rowsecurity = true`.

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

The desktop app keeps its local SQLite database. Cloud account
integration (login from the desktop app, license verification) is a
**future step** — do not wire the desktop pipeline to Supabase yet.
