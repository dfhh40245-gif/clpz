# Studio interface refresh — September 2026

## Android

Native Compose studio with a local guest entry, shared account sign-in, thumbnail library, search, sorting, draft duplication and deletion, and a resume-editing action. Imports create editable start/middle/end drafts, not AI-selected semantic moments.

The editor has Cut, Text, and Frame panels; real effect preview; draft autosave; undo/redo; caption styles and positions; aspect ratios; and mute. Export uses the same effects as preview and offers progress, cancellation, Android Save, and Share.

The preview APK uses a cached debug signing key. An older preview signed with another key cannot be upgraded in place; uninstalling removes local drafts. A managed production signing key remains a release task.

## Website

Responsive navigation and a dedicated `/apps` page distinguish Windows and Android downloads. Shared navigation extends to account, checkout status, legal, and missing-page screens. The landing page keeps its pearl CTA and product showcase, with clearer download cards, FAQ, and readable light/dark styling. The login background keeps pointer interaction; the landing gradients remain autonomous.

Payment plans are visibly marked as coming soon because Gumroad setup is incomplete. Account pages do not invent a credit balance. Downloads are free; optional credits are separate.

## Desktop

The active interface is `frontend/clpz.html`, served by the packaged local backend. It now has an import-focused studio, larger controls, neutral surfaces, project search, thumbnail project cards, and an improved editor layout. Edit choices persist in localStorage by job and clip; original media is unchanged. Undo/redo and keyboard shortcuts are available. Audio and speed affect preview, and trim bounds are enforced. Text overlays and amplification above 100% are applied at export, with explanatory copy in the editor.

## Verification

- Website production build and ESLint.
- `scripts/interface-check.cjs`: browser checks for mobile navigation, theme switching, password visibility, responsive overflow, desktop draft reopening, undo/redo, and search. Desktop APIs use fixture data; this is not an end-to-end media pipeline or payment test.
- Android workflow: compile the APK, then run device tests using generated video to exercise auth controls, the library, editor autosave/undo, and a playable trimmed square export. Device screenshots and test reports are workflow artifacts.
- Windows package audit, followed by an Inno Setup installer build using the existing engine binaries and refreshed active frontend.

## Remaining integration work

Gumroad product setup and payment verification, mobile semantic AI, project syncing, and validation of the Supabase Android OAuth redirect remain separate work. The current changes must not be described as completing these integrations.
