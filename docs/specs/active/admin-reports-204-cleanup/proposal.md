---
slug: admin-reports-204-cleanup
title: Admin Reports Cleanup Plan
description: Round 5 delivery and manifest-controlled cleanup plan
status: active
branch: origin/main
created: 2026-07-12
updated: 2026-08-06
tags: [scraper, web, data-integrity]
---

## Goal

Reduce the live pending Admin Reports queue by fixing the owning writers, detectors, and lifecycle paths first, then applying only manifest-authorized repairs whose postconditions can be verified. Human reports and evidence-poor rows stay visible for manual review.

The implementation fixes writers and detectors before it changes any report status. It never runs the legacy G1 or G3 blanket cleanup scripts, and it never treats a historical row count as an execution allowlist.

The authoritative design lives at `/memories/session/plan.md`; this active spec records the checked-in Round 5 delivery state. Round 2 critique evidence remains in [notes.md](./notes.md), whose bytes stay unchanged until final archive.

## Current delivery state

Publication-policy, Round H0, and every Round G lane are delivered in `origin/main`. Their implementation steps are audit history, not active work:

* Publication-policy: `feb530e`
* H0 writer safety: `5457b5f2`
* G1 Auto-QA predicate correctness: `a2ba5bbe`
* G2 prefecture extraction and pagination: `796aa7f8`, with scheduled apply gate `56e677e2`
* G3 merger pagination: `77741cd5`
* G3 annotation-error report settlement: `e8552682`
* G4a migration, operator, and application guard series: `60978b5c` through `1295ca4d`
* G4b report status-last: `e6203c09` and `6b739a42`
* G4b deterministic performer dispatch: `90e5e9fd` and `c7f42c4c`

The next code delivery is Round G-P. It is a two-file publication annotation hotfix that unconditionally consumes `_publisher_evidence` before the payload can reach PostgREST. It includes focused tests and no production reset, report settlement, re-annotation batch, manifest apply, schema change, or data write.

Round T-P follows as a separate tools-only release. Round T-A begins only when the Admin cleanup CLI becomes a real second consumer. Phase 4 and all later data operations remain pending and require their own artifact-bound approvals.

## Historical versus executable baselines

The following counts are historical observations only. None is an apply gate, and none survives as a hard-coded execution count.

* Original planning cohort: 204 rows and 179 events
* Pre-deployment observation: 237 rows and 205 events
* Post-deployment, post-Auto-QA observation: 251 rows and 218 events
* 2026-07-29 observation: 174 rows and 154 events at 09:04 JST, denoted $B_{2026-07-29}$
* Original aggregate SHA-256: `9a91c63eaf56904580d9a7e08f0b76469e883596b1abe7812b437b49181412e2`

The original 204-row JSONL artifact is no longer available. It is absent from both the documented session-resource path and the repository; only its documented SHA-256 and aggregate statistics remain. This plan does not reconstruct it and does not extract it from any session resource.

All production writes consume a fresh immutable post-hardening ledger with full UUIDs, frozen only after Round G-P, Round T-P, the approved publication-policy data repair, and one clean pipeline cycle. The current 174-row observation is not $P_0$ and authorizes no apply. Let $P_0$ be that later fresh pending-row count. Its partition must satisfy

$$
P_0 = A + S + M
$$

where $A$ is automatic repair or reconciliation, $S$ is evidence-qualified source repair, and $M$ is manual review. No fixed 117 / 43 / 44 execution counts survive into the new manifest.

## Planning hypothesis

The remaining known publication-runtime blocker is Round G-P: `_publisher_evidence` survives finalization whenever an event already has a truthy organizer. After G-P is deployed and completes one clean authorized annotation cycle, Round T-P can provide exact reset, observed-after-image journaling, and rollback for historical publication errors. A later fully paginated scan can then partition the remaining queue into automatic, evidence-qualified source, or manual classes.

The cheapest disconfirming check for G-P is a focused truthy-organizer regression plus the first post-deploy annotation cycle. No publication payload may contain `_publisher_evidence`, and no new pure publication may fail with `PGRST204`. The cleanup disconfirming check remains the first post-hardening exact-count scan; any count mismatch, publication-policy violation, or automatic compound or payload-token proposal stops manifest generation.

## Verified current facts

The observational cutoff is `2026-07-29T00:04:45Z` (`2026-07-29 09:04:45 JST`). The fully paginated queue contains 174 pending rows, equal to `count='exact'`, with 174 unique report IDs and 154 unique event IDs. It contains 157 single-Auto rows, 15 single-human rows, and two payload or mixed manual rows.

There are 17 pending `annotation_error_stuck` reports but 18 active error events. Fourteen are `ndl_opensearch` pure publications and all 14 have a truthy organizer. Thirteen already have a pending stuck report. Event `0ee364c6-57ba-407b-90ac-10ac2b4a3608` is at retry 1 without a stuck report and is the latest proven G-P failure: its real production write failed with `PGRST204` because `_publisher_evidence` reached the `events` payload.

Diagnostic event `cfb4050b-bcec-4478-a120-5cc9d1a3198a` remains `annotated`, has retry count 0, and has no pending stuck report. Every Phase 4 reset manifest excludes it explicitly.

Production has an inactive `app_settings['admin_reports_cleanup_maintenance']` row with `updated_at='2026-07-20T05:28:42.16133+00:00'`, and the deployed `admin_reports_maintenance_active()` RPC returns `false`. Migration 094 and its predicate are applied and inactive. The authenticated, anonymous, and service-role four-quadrant evidence still must be retrieved or re-verified before the first maintenance window.

## Delivered runtime prevention audit

The following sections retain ownership history for code that is already delivered.

### Publication metadata writer safety

Publication-policy `feb530e` and H0 `5457b5f2` delivered exact-pure publication semantics, seven-field intentional-null handling, and event-report writer safety. Round G-P is a separate internal-key leak fix and does not reopen that policy.

### Auto-QA predicates and reviewed reconciliation

G1 `a2ba5bbe` delivered shared predicates, reviewed-event correctness, token-prefix classification, and compound protection.

### Backfill pagination and prefecture parsing

G2 `796aa7f8` delivered complete pagination and bounded prefecture parsing. Scheduled apply behavior is guarded by `56e677e2`.

### Merger and error-report lifecycle

G3 `77741cd5` delivered merger pagination, and `e8552682` delivered annotation-error report settlement. G4b `90e5e9fd` and `c7f42c4c` delivered deterministic performer dispatch.

### Maintenance lock and report lifecycle

G4a `60978b5c` through `1295ca4d` delivered the maintenance guard, migration 094, operator CLI, and guarded server write paths. G4b `e6203c09` and `6b739a42` delivered fail-fast, status-last report lifecycle behavior.

## Scope

### Included

* Emergency Round H0 writer-safety hotfix on the deployed publication SHA, then later manifest-controlled publication live repair
* Shared Auto-QA detection and reconciliation predicates, reviewed-event correctness, and auto-only compound protection
* Prefecture parser correctness and full pagination
* Merger input pagination, shared same-work eligibility, and annotation-error settlement
* Deterministic QA handler scheduling
* Minimum `confirmReport()` fail-fast, status-last repair
* A database-enforced maintenance lock (decision 16a), relocation of the three browser-client writers (`AdminEditClient`, `AdminEventTable`, `IsActiveToggle`) behind guarded server actions, and a canonical lock operator CLI (decision 16b)
* A fresh immutable discovery ledger, separate execution manifests, dynamic source-evidence triage, targeted cleanup, rollback snapshots, and manual review export
* Focused regression tests, full suites, dry-runs, and nightly observation

### Excluded

* Reconstructing or pretending to possess the missing 204-row JSONL
* Treating 204, 237, or 251 as a future apply count
* Rebasing or redeploying the retired unmerged publication branch, or reimplementing publication-policy logic here
* Broad source-, category-, or report-type-wide dismissal, and automatic organizer guessing
* Automatic handling of human, unknown, mixed, or payload-token compound reports, and one-off apply of any compound report even when all types are Auto-QA
* Full cross-table transaction or compensation redesign for `confirmReport()`
* Admin UI redesign, design-system changes, and any `web/messages/*.json` change
* Database migrations other than the single decision-16a maintenance-lock RESTRICTIVE RLS enforcement
* Legacy G1/G3 blanket cleanup scripts, Publication-policy Wave 2 discovery, and Eslite live identity remap unless separately approved

## The single schema migration

Migration 094 is deployed. It provides the decision-16a `SECURITY DEFINER STABLE` predicate and RESTRICTIVE write policies. The decision-16b operator CLI owns acquire and release through an atomic conditional update; the migration does not provide an acquire or release RPC.

The inactive row and false predicate result are live. Before the first maintenance window, retrieve or re-verify the full authorization matrix: authenticated and anonymous dependency writes blocked while active, anonymous lawful writes allowed while clear, service-role cleanup allowed while active, service-role interactive requests drained under the settle margin, and the lock key immutable to authenticated clients.

## Architecture decisions

1. Detection, reconciliation, and repair eligibility call the same pure predicate for each report type.
2. `report_types` classification keys on token prefixes and the known Auto-QA type set, never array length. `field:`, `fieldEdit:`, `selectionReason:`, and any unknown token are manual. A row is automatic-eligible only when every token is a known Auto-QA type.
3. A complete event-report consumer matrix is maintained. Only recurring `auto_qa.reconcile` may settle an all-known-Auto-QA compound, and only when every predicate resolves. `qa_auto_fix`, `qa_heartbeat`, `refetch_thin_events`, error recovery, and every targeted mutation handler require exactly one known Auto-QA type.
4. For an all-known-Auto-QA compound, a deleted, inactive, reviewed, or missing event does not auto-close the row; it stays pending unless every predicate resolves. One-off cleanup rejects every compound and payload-token row.
5. `annotation_status='reviewed'` is not generic evidence of resolution. Every Auto-QA type reruns its predicate; only `annotation_error_stuck` may use verified `annotated`/`reviewed` state. The generic reviewed-to-confirm shortcut in reconcile is removed in H0.
6. A deterministic fill may touch a reviewed empty field only when it has no FC row. A non-empty FC, an empty-string intentional-empty FC, or a conflicting FC sends the row to manual review.
7. Report status is always the final Supabase write. Optional GitHub history updates are best-effort and occur only after the database result is known.
8. Automatic cleanup is keyed by full `report_id`, never event ID, type text, or UUID prefix. `uuid` columns never use `.like()`.
9. `field_corrections.corrected_value` never receives SQL NULL. Scalar intentional emptiness uses `""`; arrays and objects use JSON text through existing helpers.
10. Every full-table read paginates, compares accumulated rows with an exact count, and uses deterministic ordering. Ledger freeze requires two consecutive full scans with byte-identical normalized output while writers are paused.
11. Interactive dependency writers are mutually excluded from cleanup windows by the decision-16a maintenance lock, enforced at the database and at the top of each handler, with the decision-16b operator CLI as the lock's sole lifecycle owner.
12. Cleanup artifacts have three stages: immutable discovery ledger, one versioned classification artifact with embedded reclassification history, and an immutable per-batch apply manifest. Only the last stage is approvable for writes.
13. Every production approval binds to one existing artifact digest, exact row and action counts, deployed SHA, snapshot destination, writer-freeze record SHA, and one literal command. An approval never covers a future manifest or reconcile result.
14. Fixed venues use `venue_registry`; no new hardcoded shared-venue branch is allowed. Rollback uses the existing `field_corrections_audit` journal semantics, never a broad reverse update or a legacy G1/G3 script.
15. A manifest approves a logical expected after-image. Apply immediately reads back and journals the observed physical after-image, including the trigger-generated `updated_at`; rollback eligibility compares that observed row.
16. The first scheduled writer or GPT annotation closes a reset snapshot's rollback horizon. After that point, only fix-forward or manual repair is allowed.
17. Window verification and rollback preview finish while service-role writers stay disabled. The lock is then released and verified inactive before workflows or variables are restored.
18. Restoring any service-role writer while the maintenance lock is held is forbidden because service-role clients bypass RLS.

## Release rounds

Execution is split by runtime risk. Every code release gets Engineer changes plus an independent Tester verdict; every production write gets a later digest-bound approval.

### Round H0: emergency writer-safety hotfix

Delivered in `origin/main` as `5457b5f2`. Its implementation protocol is retained only as audit history and must not be restarted from the stale H0 branch.

### Round G: residual runtime prevention

All five lanes are delivered in `origin/main`. The directory name keeps `204` for audit continuity; the count remains historical. The delivered lanes are:

* G1 — Auto-QA predicate correctness (serialized with G3 because both touch `auto_qa.py`)
* G2 — prefecture extraction and pagination
* G3 — merger and error-recovery lifecycle
* G4a — the shared web maintenance lock across every decision-16a interactive writer, the relocated browser components, and the enforcement migration
* G4b — report-lifecycle status-last plus deterministic QA scheduling

The descriptions above are acceptance history, not active implementation tasks. Publication repair also requires the deployed G3 settlement SHA, G-P, T-P, and maintenance evidence. Admin automatic cleanup requires all five lanes plus T-A.

### Round G-P: publication annotation write-path hotfix

G-P is the next code delivery. It changes only `scraper/annotator.py` and `scraper/tests/test_annotator_publication.py`. Focused regressions cover a truthy event organizer and an empty or missing organizer, requiring the internal key to be removed in both cases. The implementation pops evidence before selecting `event.organizer or evidence`.

G-P preserves publisher precedence, pure-publication null policy, registry lookup, organizer URL behavior, and all public payload semantics. It creates no cleanup manifest and authorizes no reset, report settlement, re-annotation batch, data apply, source change, workflow change, or schema change.

After separate release approval, the exact G-P SHA must complete one authorized annotation and recovery cycle with zero new publication `PGRST204` failures or internal-key leaks. This clean cycle gates Phase 4 data work, not tools-only T-P implementation.

### Round T-P: publication reset and rollback tooling

Extend `scraper/_oneoff_backfill_publication_metadata.py` in place with exact per-row error reset, logical expected after-images, immediate read-back and observed physical after-image journaling, rollback preview and apply, and failure-injection tests. Do not pre-extract `cleanup_manifest.py` or generic primitives. This is a tools-only approval and authorizes no DB writes.

### Round T-A: Admin cleanup CLI

Begin once T-P and all five G lanes are deployed. Extract policy-neutral helpers only now, when the Admin CLI is the real second consumer. Add the Admin discovery, classification, freeze, apply, rollback, and export lifecycle keyed on full report IDs. This is a tools-only approval and authorizes no DB writes.

### Round D: digest-bound production operations

Each operation has its own approval after its immutable artifact exists, and each names its prerequisite deployed SHAs. There is no blanket Round D approval.

1. Publication manifest: exact deployed H0 `5457b5f2`, G1 `a2ba5bbe`, G4a `60978b5c` through `1295ca4d`, G3 settlement `e8552682`, the exact G-P SHA plus clean authorized cycle, the exact T-P SHA, and maintenance bring-up and authorization evidence
2. Fresh Admin automatic manifest: exact deployed H0, G1, G2, G3, G4a, G4b, and T-A
3. Any source manifest: the above plus the Round S source release
4. Any reconcile-manifest approval only if an immediate reconcile is frozen into a full-ID manifest; the default is the already-authorized recurring reconcile
5. Any rollback apply approval unless pre-authorized as the response to a verified partial failure

### Round S: evidence-qualified source release

Begin only after the fresh ledger and automatic cleanup identify actual remaining source defects. Implement, test, deploy, and apply separately; deployment approval must explicitly cover or pause scheduled scraper effects before the source apply manifest is approved.

## Phase 4 publication repair

No publication data write begins until an immutable manifest receives its own approval. The manifest selects still-error pure publications by full event and pending-report UUID and explicitly excludes `cfb4050b-bcec-4478-a120-5cc9d1a3198a`.

The reset action approves only `annotation_status: error -> pending` and `annotation_retry_count -> 0`, with all other fields unchanged. Its compare-and-set uses the before `updated_at`, status, and retry count. The manifest stores a logical expected after-image; apply reads back and journals the observed physical after-image with the real trigger-generated `updated_at`. It does not run GPT inline or close a report.

The recovery sequence is exact reset, verification and rollback preview while writers stay disabled, lock release and inactive verification, writer restoration, one explicitly authorized normal annotation cycle under deployed G-P, then report settlement only in the next `error_recovery.py` run after the shared predicate verifies `annotated` or `reviewed`. Any event that fails again remains pending or manual and is not reset repeatedly.

Every window closes in one order: keep service-role writers disabled through verification, release the owned lock and verify it inactive, then restore exact prior workflow and variable states. The first scheduled or GPT write closes the rollback horizon.

## Approval gates

* Plan approval permits implementation and validation only.
* G-P push, merge, deployment, and scheduled effects require a separate approval that authorizes no historical reset, settlement, maintenance window, or manifest apply.
* T-P and T-A each require independent tools-only approval and authorize no DB write.
* Maintenance lock and writer-state operations require maintenance-window approval and authorize no cleanup data write.
* Publication, Admin automatic, source, immediate reconcile, and rollback applies each require an approval naming an existing artifact digest and literal command.
* Final spec archive requires a separate docs-only approval.

## Affected files

### Round H0 writer-safety

* [scraper/auto_qa.py](scraper/auto_qa.py), [scraper/qa_auto_fix.py](scraper/qa_auto_fix.py), [scraper/qa_heartbeat.py](scraper/qa_heartbeat.py), [scraper/refetch_thin_events.py](scraper/refetch_thin_events.py), [scraper/error_recovery.py](scraper/error_recovery.py)
* Focused writer-safety tests under `scraper/tests/`

### Round G residual runtime

* [scraper/auto_qa.py](scraper/auto_qa.py), [scraper/backfill_location_prefectures.py](scraper/backfill_location_prefectures.py), [scraper/merger.py](scraper/merger.py), [scraper/error_recovery.py](scraper/error_recovery.py), [scraper/qa_auto_fix.py](scraper/qa_auto_fix.py)
* [web/app/actions/confirm-report.ts](web/app/actions/confirm-report.ts), [web/app/actions/dismiss-report.ts](web/app/actions/dismiss-report.ts), [web/app/actions/submit-report.ts](web/app/actions/submit-report.ts), [web/app/actions/admin-events.ts](web/app/actions/admin-events.ts), [web/app/actions/owner-events.ts](web/app/actions/owner-events.ts), [web/app/actions/works.ts](web/app/actions/works.ts)
* [web/components/AdminEditClient.tsx](web/components/AdminEditClient.tsx), [web/components/AdminEventTable.tsx](web/components/AdminEventTable.tsx), [web/components/IsActiveToggle.tsx](web/components/IsActiveToggle.tsx) — browser-client dependency writes relocated behind guarded server actions
* The `annotate-event`, `review-status`, `annotate-now`, `scrape-now`, and `enrich-and-annotate` API routes — maintenance-lock guard before write or dispatch
* New `web/lib/maintenanceLock.server.ts` (`assertWritesAllowed` only), a shared service-role client helper, `supabase/migrations/<NNN>_admin_reports_maintenance_lock.sql`, and `scraper/_oneoff_admin_reports_maintenance.py` (decision-16b operator CLI)
* New web tests for status-last, CAS, fail-closed lock, and the in-flight race; new scraper lock-atomicity fixtures
* This `proposal.md` and `tasks.md`; `notes.md` preserved unchanged until archive

### Round G-P publication hotfix

* `scraper/annotator.py`
* `scraper/tests/test_annotator_publication.py`
* No workflow, schema, web, translation, source, or production-data change

### Round T tooling

* T-P extends `scraper/_oneoff_backfill_publication_metadata.py` in place with exact reset, observed-after-image journal, rollback preview and apply, and failure-injection tests
* T-A extracts shared helpers only when it adds `scraper/_oneoff_cleanup_admin_reports.py` as a real second consumer

### Conditional files

Change only after a focused reproduction proves ownership: the scraper, merger, recovery, and QA workflows, `scraper/main.py`, and source files selected by the fresh evidence inventory. Do not modify `web/messages/*.json` in any residual or tooling release.

## Verification commands

Run from the isolated worktree using the repository-root `.venv/bin/python`:

```bash
PYTHON="/Users/flyingship/development/Tokyo Taiwan Radar/.venv/bin/python"
"$PYTHON" -m pytest scraper/tests/test_annotator_publication.py -q
"$PYTHON" -m pytest scraper/tests
"$PYTHON" -m compileall -q scraper
git diff --check
```

Also validate frontmatter and Markdown when repository tooling is available, grep for stale Round 4 topology, prove `notes.md` SHA-256 is unchanged, and verify exactly the four approved delivery files are modified. This delivery has no `web/messages/` diff and performs no production DB write.

## Rollback and stop conditions

Stop immediately when HEAD or production counts drift unexpectedly before apply, an unexpected report type appears in a manifest, an event / FC row / merge participant / report differs from its recorded before-image, a source page contradicts the proposed repair, any verification fails, a report would close while its predicate still fires, a merge target is inactive or cross-work or creates a cycle, any automatic batch reaches a human or compound report, or Tester returns FAIL. Rollback uses the frozen snapshot and audit journal only.

## Definition of done

* G-P, T-P, T-A, and any required Round S release are independently tested and deployed.
* G-P proves the internal key cannot survive finalization, and one clean authorized cycle creates no new publication `PGRST204` failure.
* Phase 4 and later applies use digest-bound immutable manifests, complete before-images, logical expected after-images, observed physical after-image journals, exact row counts, snapshots, and literal apply and rollback commands.
* A fresh $P_0=A+S+M$ partition is verified, and no one-off automatic batch contains a compound, human, mixed, unknown, empty, or payload-token row.
* Every maintenance window releases the lock and verifies it inactive before restoring service-role writers.
* Human and evidence-poor rows have a digest-bound manual export, and final scheduled observation recreates no repaired defect.
* Every push, deployment, scheduled effect, maintenance operation, and production apply receives its stated approval.
* Only after all closeout gates pass does the spec move to `docs/specs/archive/<YYYY-MM>-admin-reports-204-cleanup/`, with `notes.md` preserved.
