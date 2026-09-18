# Task 20 — Make Android preview reliable and accurately described

Task: 20 (Android readiness)
Commit: 76e4b0a (baseline; tasks 01–20 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-18
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Kotlin 2.1.20 / AGP 8.10.1 (project-declared); **no Android SDK, Gradle or emulator on this machine** (see Remaining blockers)

## Original reproduction

- Suggestions were fixed start/middle/end timeline windows but presented as generic "moment drafts"; audit F25 notes they are not semantic analysis.
- `saveAll` appended rows unconditionally (`write(load() + projects)`), so repeated saves duplicated project IDs.
- `VideoExporter.cancel()` deleted the output but left the completion callback armed: a cancelled run could still deliver a result, and `exported?.let { file -> ... }` UI state could report success after cancel.
- CI published the debug APK to the `mobile-latest` release *before* the separate interface-checks job ran (`needs:` was absent on the publish step).

## Files changed

- `mobile-android/app/src/main/java/com/clpz/mobile/ProjectStore.kt` — `draftKind` field ("timeline"/"manual"); `ProjectLogic` pure core (idempotent `mergeById`, `timelineSuggestions`); `isSourceAvailable()` distinguishing file:// existence and content:// persisted grants; legacy rows default to `draftKind="timeline"`.
- `mobile-android/app/src/main/java/com/clpz/mobile/VideoExporter.kt` — cancel sets a flag before `transformer.cancel()`, suppresses terminal callbacks, deletes partial output; `isBusy` guard rejects double export with `IllegalStateException`.
- `mobile-android/app/src/main/java/com/clpz/mobile/EditorScreen.kt` — cancel path shows a "Nothing was saved from this attempt" snackbar; export dialog blocks dismissal so cancellation is user-initiated.
- `.github/workflows/android-apk.yml` — fail-closed publication: `publish` needs `[build, interface-checks]`; production channel is a separate manual job (`environment: production-android`, release keystore secrets, AAB); JVM unit-test job added.
- `mobile-android/app/build.gradle.kts` — release signing config activates only when CI keystore secret present; JVM test deps (JUnit, org.json, Robolectric).
- `mobile-android/app/src/test/java/com/clpz/mobile/ProjectStoreTest.kt` — 7 JVM tests (idempotency, ordering, timeline labeling, clamping, round-trip, legacy default).
- `mobile-android/app/src/test/java/com/clpz/mobile/VideoExporterTest.kt` — 4 Robolectric tests (cancel safety, failed export leaves no file/no success, double-export rejection, empty clip rejection).
- `mobile-android/README.md` — timeline-draft scope wording, wrapper commands, fail-closed CI description, preview vs production channel and keystore handling.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Import/save/kill/reopen/export on min + current Android | on-device/emulator run of `StudioFlowTest` | succeeds | NOT RUN — no SDK/emulator on this machine | NOT RUN | this file |
| Source permission loss recoverable; no duplicate IDs | JVM: `saveAll is idempotent`; `isSourceAvailable` distinguishes lost sources | no dupes; recoverable state surfaced | logic implemented + unit-tested on JVM; on-device recovery flow NOT RUN | PARTIAL (logic PASS, device NOT RUN) | ProjectStoreTest.kt |
| Cancel/delete during export cleans partial files, no false success | JVM: exporter cancel contract tests | callback suppressed; partial deleted | implemented; Robolectric tests written but **not executed** (no Gradle) | PARTIAL (code + tests present, NOT RUN) | VideoExporterTest.kt |
| Failed interface test prevents publication; signed upgrades preserve projects | CI graph: `publish` needs `[build, interface-checks]`; production job gated | publication blocked on red checks | workflow restructured; CI run NOT OBSERVED (no push authorization) | PARTIAL | android-apk.yml |

## Migration and rollback

`draftKind` is additive; rows written by older builds load with the default and remain valid. Rollback = revert the working-tree changes; old build ignores the new JSON key.

## Remaining blockers

1. No Android SDK, Gradle, or emulator on this machine — JVM/Robolectric tests are written but unexecuted; `StudioFlowTest` needs a device run. Prerequisite: Android Studio/SDK + JDK 17, then `gradle :app:testDebugUnitTest` and `bash mobile-android/check-interface.sh`.
2. Production signing requires the owner to create the keystore and the four CI secrets; upgrade preservation must be verified with a real signed upgrade (install v0.2.0 debug → install v0.2.1 signed → confirm projects/session survive).
3. CI behavior must be observed on a real push; this workspace was not authorized to push.

Artifact name and SHA-256: n/a (no APK built on this machine).
Reviewer: —
