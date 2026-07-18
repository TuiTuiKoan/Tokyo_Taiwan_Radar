---
slug: admin-reports-204-cleanup
title: Admin Reports Cleanup Plan
status: active
branch: feat/admin-reports-204-cleanup
created: 2026-07-12
updated: 2026-07-18
tags: [scraper, web, data-integrity]
---

## Goal

Reduce the live pending Admin Reports queue by fixing the owning writers, detectors, and lifecycle paths first, then applying only manifest-authorized repairs whose postconditions can be verified. Human reports and evidence-poor rows stay visible for manual review.

The implementation fixes writers and detectors before it changes any report status. It never runs the legacy G1 or G3 blanket cleanup scripts, and it never treats a historical row count as an execution allowlist.

This revision supersedes the retired fixed-count Wave A/B topology. The authoritative design lives at `/memories/session/plan.md`; this spec tracks the parts that touch the checked-in repository. Round 2 critique evidence remains in [notes.md](./notes.md).

## Historical versus executable baselines

The following counts are historical observations only. None is an apply gate, and none survives as a hard-coded execution count.

* Original planning cohort: 204 rows and 179 events
* Pre-deployment observation: 237 rows and 205 events
* Post-deployment, post-Auto-QA observation: 251 rows and 218 events
* Original aggregate SHA-256: `9a91c63eaf56904580d9a7e08f0b76469e883596b1abe7812b437b49181412e2`

The original 204-row JSONL artifact is no longer available. It is absent from both the documented session-resource path and the repository; only its documented SHA-256 and aggregate statistics remain. This plan does not reconstruct it and does not extract it from any session resource.

All production writes consume a fresh immutable post-hardening ledger with full UUIDs, frozen only after Round H0, Round G, the approved publication-policy data repair, and one clean pipeline cycle. Let $P_0$ be that fresh pending-row count. Its partition must satisfy

$$
P_0 = A + S + M
$$

where $A$ is automatic repair or reconciliation, $S$ is evidence-qualified source repair, and $M$ is manual review. No fixed 117 / 43 / 44 execution counts survive into the new manifest.

## Planning hypothesis

Publication-policy is already merged and deployed at `feb530e`, but with incomplete writer safety. After the emergency Round H0 writer-safety hotfix and the residual Round G prevention fixes are deployed, a fully paginated post-hardening scan can partition every pending row into automatic, evidence-qualified source, or manual classes.

The cheapest disconfirming check is the first post-hardening exact-count scan. If it still finds pure publications with physical venue or hour fields, publication QA rows whose shared predicates still fire, compound or payload-token rows proposed for automatic closure, or fetched counts that differ from `count='exact'`, execution stops before a cleanup manifest is generated.

## Residual defects (owners of the current queue)

Counts in this section are historical observations, not apply gates. They describe the classes of defect each round must fix.

### Publication metadata writes physical-field placeholders

[scraper/annotator.py](scraper/annotator.py) and [scraper/_oneoff_backfill_publication_metadata.py](scraper/_oneoff_backfill_publication_metadata.py) historically wrote purchase or publication labels into `location_name`, `location_address`, and `business_hours`. A publication has no physical venue; purchase guidance belongs in descriptions, URLs, or verified price metadata. Publication-policy `feb530e` already deploys most of this fix; the residual writer-safety debt is Round H0's first priority.

### Auto-QA predicates and reviewed reconciliation are unsafe

[scraper/auto_qa.py](scraper/auto_qa.py) still carries a generic reviewed-to-confirm shortcut and predicate-level reviewed skips that can close an unresolved row. The missing-hours, missing-performers, thin-content, and same-work predicates are broader than the data semantics, and `report_types` classification must key on token prefixes and the known Auto-QA set rather than array length.

### Backfill pagination and prefecture parsing are incomplete

[scraper/backfill_location_prefectures.py](scraper/backfill_location_prefectures.py) performs unpaginated full-table queries that Supabase can cap at 1,000 rows, silently skipping later events. Its anchored parser misses labelled strings such as `住所は東京都...` and can mistake Taiwan aliases such as `新北` inside a Japanese address.

### Merger input and error-report lifecycle drift

[scraper/merger.py](scraper/merger.py) does not fully paginate active-event inputs, so later passes can miss pairs beyond the first Supabase page. [scraper/error_recovery.py](scraper/error_recovery.py) resets retry counters but never confirms `annotation_error_stuck` reports after an event becomes `annotated` or `reviewed`, and [scraper/qa_auto_fix.py](scraper/qa_auto_fix.py) does not run its deterministic performer handler in the normal daily path.

### `confirmReport()` write ordering is unsafe

[web/app/actions/confirm-report.ts](web/app/actions/confirm-report.ts) can set report status before its event and correction writes are verified, and it trusts client-supplied `eventId`/`reportTypes`. Report status must be the final write, guarded by a pending compare-and-set.

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

This plan requires exactly one migration and no other schema change. It supersedes the earlier "no schema change is required" statement.

The decision-16a maintenance-lock enforcement adds a `SECURITY DEFINER STABLE` predicate `admin_reports_maintenance_active()` with a fixed `search_path` and restricted `EXECUTE`, one RESTRICTIVE `INSERT`/`UPDATE`/`DELETE` policy per table on `events`, `event_reports`, `field_corrections`, `category_corrections`, `selection_reason_corrections`, and `works`, plus a RESTRICTIVE policy protecting the `admin_reports_cleanup_maintenance` `app_settings` key from `authenticated` write. The same migration adds the decision-16b atomic acquire/release primitive (an RPC or conditional `UPDATE`).

Because these are RESTRICTIVE policies they AND with the existing permissive policies, so a non-service write is blocked at statement time while the lock is active without touching `SELECT` visibility; service-role bypasses RLS for the controlled cleanup client. A missing row, read error, or malformed value fails closed. The migration's sequence number must match the current `.github/instructions/database.instructions.md` "next" value, updated in the same commit.

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
12. Cleanup artifacts have four stages: immutable discovery ledger, mutable classification workspace, append-only hash-chained decision log, and immutable per-batch apply manifest. Only the last stage is approvable for writes.
13. Every production approval binds to one existing artifact digest, exact row and action counts, deployed SHA, snapshot destination, writer-freeze record SHA, and one literal command. An approval never covers a future manifest or reconcile result.
14. Fixed venues use `venue_registry`; no new hardcoded shared-venue branch is allowed. Rollback uses the existing `field_corrections_audit` journal semantics, never a broad reverse update or a legacy G1/G3 script.

## Release rounds

Execution is split by runtime risk. Every code release gets Engineer changes plus an independent Tester verdict; every production write gets a later digest-bound approval.

### Round H0 — emergency writer-safety hotfix

Publication-policy is already deployed. After the standalone tracked-spec docs-only commit (this file plus `tasks.md`) merges, create branch `fix/event-report-writer-safety` and an isolated worktree based on the resulting `origin/main`, with deployed `feb530e` verified as an ancestor.

H0 removes the generic reviewed-to-confirm shortcut and predicate-level reviewed skips in `auto_qa.reconcile()`, adds token-prefix-aware all-known-Auto eligibility, enforces the compound lifecycle invariant, inventories every `event_reports` reader/writer into a consumer matrix, and adds shared single-type eligibility plus a pending compare-and-set to `qa_auto_fix`, `qa_heartbeat`, `refetch_thin_events`, and error-recovery settlement. A read-only production impact ledger is frozen before any production code edit.

### Round G — residual runtime prevention (five lanes)

Round G runs in `ttr-admin-reports-204-cleanup-worktree` on `feat/admin-reports-204-cleanup`, created only after Round H0 is in `origin/main`. The directory name keeps `204` for audit continuity; the count is historical. Round G is organized into decoupled dependency lanes:

* G1 — Auto-QA predicate correctness (serialized with G3 because both touch `auto_qa.py`)
* G2 — prefecture extraction and pagination
* G3 — merger and error-recovery lifecycle
* G4a — the shared web maintenance lock across every decision-16a interactive writer, the relocated browser components, and the enforcement migration
* G4b — report-lifecycle status-last plus deterministic QA scheduling

The default is one Round G release when every lane is green; a green lane may ship as its own Tester-passed sub-release to unblock its downstream manifest while a red lane is fixed. The publication manifest requires only G1 and G4a plus Round T-P; the Admin automatic manifest requires all five lanes plus Round T-A. Before G3, resolve ownership of `scraper/merger.py` against the `merger-multi-signal-pass4` spec so two efforts never edit it at once.

### Round T-P — shared primitives and publication rollback tooling

Branch `feat/admin-reports-cleanup-primitives` on the deployed `origin/main` once H0, G1, and G4a are ancestors. Extract reusable immutable-artifact, pagination, snapshot, drift, journaled-write, and after-image helpers from the publication manifest and `unlock_and_write()`, and add executable publication rollback. This is a tools-only approval; it authorizes no DB writes.

### Round T-A — Admin cleanup CLI

Branch `feat/admin-reports-cleanup-tooling` on the deployed `origin/main` once T-P and all five G lanes are ancestors. Reuse the T-P primitives and add the Admin discovery/classify/freeze/apply/rollback/export CLI, keyed on full report IDs. This is a tools-only approval; it authorizes no DB writes.

### Round D — digest-bound production operations

Each operation has its own approval after its immutable artifact exists, and each names its prerequisite deployed SHAs. There is no blanket Round D approval.

1. Publication manifest — prerequisites: H0, G1, G4a, T-P
2. Fresh Admin automatic manifest — prerequisites: H0, G1, G2, G3, G4a, G4b, T-A
3. Any source manifest — the above plus the Round S source release
4. Any reconcile-manifest approval only if an immediate reconcile is frozen into a full-ID manifest; the default is the already-authorized recurring reconcile
5. Any rollback apply approval unless pre-authorized as the response to a verified partial failure

### Round S — evidence-qualified source release

Begin only after the fresh ledger and automatic cleanup identify actual remaining source defects. Implement, test, deploy, and apply separately; deployment approval must explicitly cover or pause scheduled scraper effects before the source apply manifest is approved.

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

### Round T tooling

* New shared `scraper/cleanup_manifest.py` (or repository-consistent equivalent), `scraper/_oneoff_backfill_publication_metadata.py` adapted to shared primitives, new `scraper/_oneoff_cleanup_admin_reports.py`, and dedicated manifest/apply/rollback/failure-injection tests

### Conditional files

Change only after a focused reproduction proves ownership: the scraper, merger, recovery, and QA workflows, `scraper/main.py`, and source files selected by the fresh evidence inventory. Do not modify `web/messages/*.json` in any residual or tooling release.

## Verification commands

Run from the isolated worktree using the repository-root `.venv/bin/python`:

```bash
python -m pytest scraper/tests
python -m compileall -q scraper
cd scraper && python auto_qa.py --reconcile --dry-run
cd scraper && python auto_qa.py --dry-run
cd scraper && python qa_auto_fix.py --dry-run
cd scraper && python qa_heartbeat.py --dry-run --limit 20
cd scraper && python refetch_thin_events.py --dry-run --limit 20
cd scraper && python error_recovery.py --dry-run --limit 100
cd scraper && python backfill_location_prefectures.py --dry-run
cd scraper && python merger.py --dry-run
```

For every modified source: `cd scraper && python main.py --dry-run --source <source_name>`.

Read-only production verification must prove the accumulated paginated count equals `count='exact'`, every classification keys on full report ID and token prefix, no automatic batch contains a human or compound report, the only migration in scope is the decision-16a lock, and no change exists under `web/messages/`.

## Rollback and stop conditions

Stop immediately when HEAD or production counts drift unexpectedly before apply, an unexpected report type appears in a manifest, an event / FC row / merge participant / report differs from its recorded before-image, a source page contradicts the proposed repair, any verification fails, a report would close while its predicate still fires, a merge target is inactive or cross-work or creates a cycle, any automatic batch reaches a human or compound report, or Tester returns FAIL. Rollback uses the frozen snapshot and audit journal only.

## Definition of done

* Round H0 is deployed and the read-only impact ledger is frozen with dual protected copies and matching SHA-256.
* Round G lanes G1–G4b are deployed per their downstream-manifest prerequisites, and the decision-16a maintenance-lock migration plus the decision-16b operator CLI are in place.
* Rounds T-P and T-A install primitives, publication rollback, and the Admin cleanup CLI with no DB writes.
* Every production write in Round D uses a digest-bound approval over an immutable manifest, and the fresh $P_0 = A + S + M$ partition is verified.
* Human and evidence-poor rows are exported for manual review; no Python apply path can close them.
* A fresh scan and one nightly cycle do not recreate resolved rows after each deployment cycle, and Tester returns PASS for every modified scraper, web action, and workflow path.
* Each push occurs only after explicit user approval. The spec directory is then archived to `docs/specs/archive/<YYYY-MM>-admin-reports-204-cleanup/` with `notes.md` preserved.
