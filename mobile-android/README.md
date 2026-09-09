# CLPZ Mobile

Native Android editor for creating, saving, reopening, and exporting clips on-device.

## Configure

Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `WEBSITE_URL` in the build environment. The first two values must point to the same Supabase project used by the CLPZ website.

Add `clpz://auth` to **Authentication → URL Configuration → Redirect URLs** in Supabase. Enable Email and Google providers in the same project. The Google provider uses the existing Supabase OAuth configuration; Android returns to the app through the `clpz://auth` deep link.

## Build

Open this directory in Android Studio, or run the **Android APK** GitHub Actions workflow. The debug APK is uploaded as the `CLPZ-Mobile-debug` workflow artifact.

For GitHub Actions, create repository secrets named `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The workflow publishes the installable file as `CLPZ-Mobile.apk` in the `mobile-latest` prerelease, which powers the website's `/download/android` route.

## Current editing scope

- Imports a video with persistent Android document access.
- Creates three editable moment drafts across the source timeline. Semantic AI moment detection still requires the hosted analysis service.
- Saves trim, caption, and aspect-ratio choices locally.
- Reopens drafts later and exports trimmed MP4 files on-device with Media3 Transformer.
- Uses the shared Supabase email/password and Google identity.
- Opens CLPZ website pricing for subscription and credit entitlements.
