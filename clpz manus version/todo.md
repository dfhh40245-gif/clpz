# Project TODO

- [x] Establish the CLPZ dark visual design system, typography, responsive shell, and accessible focus behavior.
- [x] Build minimal top navigation with exactly Create, Projects, and Settings actions, including Settings placeholder notification.
- [x] Implement the creation screen with validated YouTube URL entry, Forge action, video file picker, drag-and-drop support, and selected-file details.
- [x] Implement staged job processing UI with sequential Download, Transcription, Analysis, Clip selection, and Rendering progress plus recovery states.
- [x] Define persistent project and clip data models, local video upload endpoint, and job lifecycle procedures. Scope removed: UI-only request.
- [x] Build responsive strict-9:16 clip cards with on-demand playback previews, score badge, edit, download, and focused viewing actions.
- [x] Create the clip viewer modal with playback, scrubber timeline, and metadata.
- [x] Create the integrated editor shell with placeholder Text, Image, Music, and Crop tools; caption property controls; preview; and timeline architecture.
- [x] Build the Projects screen with previous-job cards and an intentional empty state.
- [x] Add subtle toast states for uploads, errors, retry paths, download feedback, and deferred settings.
- [x] Resolve and re-verify the clip-card semantic nesting issue identified during browser console inspection.
- [ ] Verify keyboard navigation end-to-end across Create, Projects, the clip viewer, and the editor shell, including visible focus treatment.
- [ ] Re-run browser-console QA across the clips grid, clip viewer, and editor shell after the accessibility fix.
- [x] Write and run automated tests for core job/state helpers and verify responsiveness.
- [x] Deliver CLPZ as a UI-only implementation: interactive client-side demo states only, with no video-processing backend or database changes.
