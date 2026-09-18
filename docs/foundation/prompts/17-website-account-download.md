# Task 17 — Complete the website account and download journey

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P1.
Prerequisites: task 01, task 02, task 14, task 15, task 16.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The current website builds and lints successfully, and its Google action exists. Account page only offers downloads; password recovery is absent from the form. Download destinations and Vercel build-root instructions differ across files. A local Node URL probe shows that next=/\\untrusted.example passes the callback guard but resolves to an external origin; this is a confirmed validation defect, not a demonstrated stolen session.

## Inspect these files

- website/app/login/auth-form.tsx
- website/app/login/google-button.tsx
- website/app/auth/callback/route.ts
- website/app/account/page.tsx
- website/app/download/route.ts
- website/app/download/android/route.ts
- website/.env.example
- website/vercel.json
- vercel.json

## Implementation steps

1. Complete confirmation, login/logout, expired session, password reset/recovery and provider-error states with accessible feedback.
2. Show real subscription/credits/entitlements from the cloud contract. Do not display a successful purchase merely because the browser returned from checkout.
3. Resolve one deployment-root convention with deterministic installs and validated configuration; make missing config and unavailable downloads understandable.
4. Choose one release source per platform, validate URLs and artifact versions/hashes, distinguish Android preview from stable Windows, and test redirect safety including slash/backslash-encoded callback variants.
5. Fix callback redirects by resolving against the approved origin and checking the normalized destination origin/path, rather than relying on startsWith alone. Test the URL logic without requiring real OAuth credentials.

## Acceptance checks — all required for this task

- [ ] New user confirmation, Google sign-in, forgotten password, logout and expired callback all have browser-test coverage.
- [ ] Account data is isolated by user and updates after verified fulfillment.
- [ ] Download links resolve to the intended tested artifact in staging; a missing artifact produces useful UI.
- [ ] Keyboard/mobile-width/accessibility checks pass; both build and production serving work using the documented root/settings.
- [ ] Backslash, double-slash, encoded and absolute external next values cannot redirect outside the site after OAuth; approved relative paths still work.

## Deliverables and handoff

Complete account/download flows, configuration/runbook, and browser/staging test evidence.

Create or update docs/foundation/evidence/task-17.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

