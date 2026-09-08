# CLPZ storefront deployment

The public storefront is the Next.js application in `website/`. Video processing stays inside the desktop or mobile application and is not deployed to Vercel.

## Vercel

Import the GitHub repository with the repository root as the project root. The root `vercel.json` runs the install and build commands inside `website/`.

Add these variables to Production, Preview, and Development unless a narrower scope is intentional:

| Variable | Visibility | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_SITE_URL` | Public | Canonical production origin |
| `NEXT_PUBLIC_SUPABASE_URL` | Public | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public | Supabase browser-safe anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret | Server-only payment persistence |
| `GUMROAD_PRODUCT_URL` | Server | Gumroad product page |
| `GUMROAD_PRODUCT_ID` | Server | Gumroad license/product identifier |
| `GUMROAD_PRODUCT_PERMALINK` | Server | Expected Ping product permalink |
| `GUMROAD_PING_SECRET` | Secret | Long random token in the Ping callback URL |
| `DOWNLOAD_URL` | Server | Versioned GitHub Release installer URL |

After deployment, verify `/api/health`. It reports configuration booleans and never returns secret values.

## Supabase

Create one project, then apply `supabase/migrations/0001_initial_schema.sql`. The schema keeps payment and entitlement writes behind the service-role key and exposes only published release metadata to anonymous visitors.

Never place `SUPABASE_SERVICE_ROLE_KEY` in a `NEXT_PUBLIC_` variable or commit a real value to the repository.

### Google login

In Supabase Auth URL Configuration, set the Site URL to `https://clpzit.vercel.app` and add `https://clpzit.vercel.app/auth/callback` to the redirect allow list.

In Google Auth Platform, create a Web application OAuth client with:

- Authorized JavaScript origin: `https://clpzit.vercel.app`
- Authorized redirect URI: `https://YOUR_SUPABASE_PROJECT_REF.supabase.co/auth/v1/callback`
- Scopes: `openid`, `userinfo.email`, and `userinfo.profile`

Copy the resulting client ID and client secret into Supabase Authentication > Providers > Google, then enable the provider. The Google client secret belongs only in Supabase and must not be added to the website or Vercel.

## Gumroad

Create a digital product for CLPZ and add a license-key block if license enforcement will be enabled in the applications. Set the Advanced Settings Ping URL to:

`https://YOUR_DOMAIN/api/gumroad/ping?token=YOUR_GUMROAD_PING_SECRET`

Set `GUMROAD_PRODUCT_PERMALINK` to the product URL suffix. The handler rejects a mismatched product and writes each Gumroad `sale_id` idempotently into Supabase.

Attach the signed Windows installer to a GitHub Release and set `DOWNLOAD_URL` to that exact asset. Do not commit the installer binary into Git.
