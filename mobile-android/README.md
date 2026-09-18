# CLPZ Mobile

Native Android editor for creating, saving, reopening, and exporting clips on-device.

## Configure

Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `WEBSITE_URL` in the build environment. The first two values must point to the same Supabase project used by the CLPZ website.

Add `clpz://auth` to **Authentication → URL Configuration → Redirect URLs** in Supabase. Enable Email and Google providers in the same project. The Google provider uses the existing Supabase OAuth configuration; Android returns to the app through the `clpz://auth` deep link.

## Build

Local builds use the committed Gradle wrapper:

```bash
cd mobile-android
./gradlew :app:assembleDebug        # debug APK
./gradlew :app:testDebugUnitTest    # JVM unit tests (store/exporter logic)
./gradlew :app:connectedDebugAndroidTest  # on-emulator interface checks
```

CI (**Android APK** workflow) is fail-closed: the `mobile-latest` preview release is published only after the build **and** the on-emulator interface checks both succeed. A deliberately failing interface test blocks publication.

### Preview vs production channels

- **Preview**: debug-signed `CLPZ-Mobile.apk` in the `mobile-latest` prerelease.
- **Production**: manual `workflow_dispatch` with `run_production=true`, gated on the same build+interface jobs and an `environment: production-android` approval. Requires repository secrets `ANDROID_RELEASE_KEYSTORE_B64` (base64 keystore), `ANDROID_RELEASE_STORE_PASSWORD`, `ANDROID_RELEASE_KEY_ALIAS`, `ANDROID_RELEASE_KEY_PASSWORD`. Keys stay outside source and APKs; the same keystore must be reused for every upgrade so Android treats new versions as updates of the same identity.

For GitHub Actions, create repository secrets named `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The workflow publishes the installable file as `CLPZ-Mobile.apk` in the `mobile-latest` prerelease, which powers the website's `/download/android` route.

## Current editing scope

- Imports a video with persistent Android document access.
- Creates three editable moment drafts across the source timeline. These are **timeline drafts** — fixed start/middle/end windows — not semantic/AI moment detection; that would be a separate, evaluated feature.
- Saves trim, caption, and aspect-ratio choices locally.
- Reopens drafts later and exports trimmed MP4 files on-device with Media3 Transformer.
- Uses the shared Supabase email/password and Google identity.
- Opens CLPZ website pricing for subscription and credit entitlements.
