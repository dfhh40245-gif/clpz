# CLPZ — start here

This is the implementation foundation you requested: **what to fix, what to add, the order to do it, and a complete prompt for each task**. It is based on the current repository and your diagram, checked on **17 September 2026**, baseline commit **76e4b0a**.

Application source was not changed. This folder contains the audit, proposed contracts, 22 implementation prompts, acceptance criteria and reproducible evidence. OPEN means the task has been specified, not implemented.

## The main conclusion

The project already has useful components. The next work is to connect and harden them into one dependable product. Start with reproducible checks and security, then repair processing/export/recovery, then finish packaging and commercial account flows.

The largest immediate problems are:
- Local admin bootstrap and local API boundaries need protection.
- Retrying after analysis crashes; muted and quarter-speed exports fail.
- Duplicate refunds and repeated backups fail.
- The installed server path disagrees with the launcher; the bundled downloader does not start on the audit machine.
- Website payment recording does not fulfill purchases or link them to accounts.
- Desktop identity/credits are separate from the website/Android cloud identity.
- The diagram and documentation overstate or omit important connections.

Some old findings are already partly fixed. Read the current audit before repeating old work.

## How anyone can use this package

1. Give the developer or coding agent access to the **whole repository**, not just the diagram.
2. Read [the audit](AUDIT.md), then [the proposed foundation](ARCHITECTURE.md).
3. Open [task 01](prompts/01-product-contract.md), copy its **entire contents**, and paste it into a coding agent with the repository open. A developer can use the same file as a work ticket.
4. Ask for the task's deliverables and evidence file. Check every acceptance item. Do not accept “done” solely because code was written or a build passed.
5. Continue through the table below, completing prerequisite task IDs first. If a task is blocked by a commercial decision or an external account, finish independent tasks while that decision is pending.
6. Finish with task 22 and [the release acceptance checklist](ACCEPTANCE.md). Keep a task OPEN/BLOCKED until its required evidence exists.

You do not need to paste all 22 prompts at once. Each is self-contained and includes scope, relevant files, exact work, tests, outputs and a completion rule. [PROMPTS.md](PROMPTS.md) collects them in one document for sharing.

For an urgent security-only pass, the callback redirect fix in task 17 and the checkout-disabled gate in task 15 can be extracted and implemented after task 02. Their independent negative tests do not require completed billing, a live provider, or the full task's later integration prerequisites. Keep the remaining integration checks OPEN.

**What “100% result” can responsibly mean:** every agreed acceptance criterion passes on the stated software versions, devices and release artifacts. No prompt can guarantee zero bugs, perfect transcription, or identical results on every machine. The foundation is designed to make completion measurable and prevent unfinished work from being called finished.

## Execution order and status

P0 is a blocker for the stated exposure/business scope; P1 is core reliability/release work; P2 is a scaling/usability improvement. These are priorities, not measured vulnerability scores. The simplest sequence is 01 through 22; the prerequisite column allows independent work to be scheduled without guessing.

| ID | Copy this prompt | Priority | Prerequisites | Status |
|---|---|---|---|---|
| 01 | [Define one product and architecture contract](prompts/01-product-contract.md) | First | — | OPEN |
| 02 | [Make setup and automated checks reproducible](prompts/02-reproducible-development.md) | P1 | 01 | OPEN |
| 03 | [Protect the desktop's local API](prompts/03-desktop-api-boundary.md) | P0 before wider exposure | 01, 02 | OPEN |
| 04 | [Fix local admin and account recovery security](prompts/04-account-security.md) | P0 for account-enabled use | 01, 02, 03 | OPEN |
| 05 | [Make failed jobs resume safely](prompts/05-pipeline-resume.md) | P1 | 02 | OPEN |
| 06 | [Fix mute, speed, trim, and text export](prompts/06-export-correctness.md) | P1 | 02 | OPEN |
| 07 | [Fix chunk overlap and transcript validation](prompts/07-transcript-integrity.md) | P1 | 02, 05 | OPEN |
| 08 | [Make local credit operations atomic](prompts/08-atomic-local-ledger.md) | P0 before relying on credits | 01, 02 | OPEN |
| 09 | [Scope retries and duplicate requests correctly](prompts/09-request-idempotency.md) | P0 before relying on credits | 02, 03, 08 | OPEN |
| 10 | [Make projects durable and backups restorable](prompts/10-durable-projects-backups.md) | P1 | 02, 05, 08, 09 | OPEN |
| 11 | [Bound heavy work and make cancellation reliable](prompts/11-bounded-media-workers.md) | P1 | 02, 05, 06, 09, 10 | OPEN |
| 12 | [Repair installed Windows startup and shutdown](prompts/12-desktop-launcher.md) | P1 release blocker | 02, 03 | OPEN |
| 13 | [Produce verified Windows installers and media tools](prompts/13-release-build-toolchain.md) | P1 release blocker | 02, 12 | OPEN |
| 14 | [Finish and test the cloud data foundation](prompts/14-cloud-schema.md) | P0 before paid cloud launch | 01, 02, 08, 09 | OPEN |
| 15 | [Connect purchases to accounts and entitlements](prompts/15-payment-fulfillment.md) | P0 before accepting payment | 01, 02, 14 | OPEN |
| 16 | [Connect desktop and mobile to shared accounts](prompts/16-shared-identity-entitlements.md) | P1 for commercial release | 01, 03, 04, 14, 15 | OPEN |
| 17 | [Complete the website account and download journey](prompts/17-website-account-download.md) | P1 | 01, 02, 14, 15, 16 | OPEN |
| 18 | [Finish the desktop editor without losing existing work](prompts/18-editor-project-contract.md) | P1 | 01, 02, 06, 07, 10, 11 | OPEN |
| 19 | [Add safe project deletion and scalable library browsing](prompts/19-project-library-storage.md) | P2 before larger libraries | 03, 09, 10, 11, 18 | OPEN |
| 20 | [Make Android preview reliable and accurately described](prompts/20-android-readiness.md) | P1 for Android launch | 01, 02, 14, 16 | OPEN |
| 21 | [Establish measurable clip quality and performance](prompts/21-media-quality-benchmarks.md) | P1 before product claims | 05, 06, 07, 11, 13, 18 | OPEN |
| 22 | [Run end-to-end acceptance and prepare operations](prompts/22-release-acceptance.md) | Final gate | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 | OPEN |

## Useful files

- [AUDIT.md](AUDIT.md): evidence, confirmed defects, unfinished additions, and audit limits.
- [ARCHITECTURE.md](ARCHITECTURE.md): current versus intended architecture, data/API contracts, decisions.
- [VERIFY.md](VERIFY.md): exact setup/check commands and troubleshooting.
- [ACCEPTANCE.md](ACCEPTANCE.md): release completion matrix.
- [PROMPTS.md](PROMPTS.md): all 22 copy-and-paste prompts.
- [backlog.json](backlog.json): machine-readable task list, dependencies and acceptance criteria.
- [evidence/current-probes.json](evidence/current-probes.json): fresh isolated reproductions.
- [evidence/baseline-checks.json](evidence/baseline-checks.json): current build/test results.
- [probe_current.py](probe_current.py): rerunnable diagnostic probes; intentionally records existing failures.

## Decisions needed before paid integration

Current website copy advertises a Creator subscription and credit packs, but implementation does not enforce the full promises. Treat existing prices/rollover claims as proposed product terms to confirm, not an instruction to change prices.

Record:
- Which release is next: free Windows local release, paid Windows release, or also Android?
- What consumes a credit: analysis request, source duration, generated clip, or another operation?
- What happens after failure, cancellation, partial success, refund, and retry?
- Does the advertised 60-day subscription rollover stay? Purchased credits are described as nonexpiring.
- What works offline, for how long, and how do multiple devices share purchased access?
- Which hardware, languages, source formats and devices are supported?

Task 01 records these decisions. No answer is needed merely to read this audit or use the independent repair prompts.
