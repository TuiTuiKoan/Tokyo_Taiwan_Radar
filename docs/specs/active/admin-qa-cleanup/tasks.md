---
title: Admin QA Cleanup Tasks
description: Successor checklist and transfer map for the remaining Admin Reports QA cleanup
---

## Tasks

This file is the execution ledger for the successor. Package A0, Package A, and
the Eslite production repair are delivered. The forward three-commit candidate
still requires final Tester validation, explicit push approval, and a later
natural scheduled observation. Every T-A0, P0, T-A1, Phase D, Phase S, and
Closeout checkbox remains unapproved. The predecessor remains immutable audit
history.

## Audit References

G-P `7c98491b8f7efd60d03c2b6d21112aca5a20389f`, G-P.1
`085d4441edf9a12eeb4ec774b84f900649f08302`, and Lane R
`fadbe289cb57d49f018d00cc22db0c5bdd87729d` are delivered `origin/main`
ancestors. T-P is retired. Runtime logs and the 2026-08-08 live rebaseline close
the bounded publication outcome, while its missing historical snapshot remains
`INCONCLUSIVE` and must not be reconstructed.

## Live Queue Observations

The historical baseline is 179 pending reports across 154 events, from two
byte-identical read-only scans on 2026-08-08. The named reports listed below were
already inside that 179-row baseline, so the queue was never 186 rows.

A separate read-only scan on 2026-08-09 counted 181 pending reports, of which 82
carried `auto_qa_missing_organizer`. Both figures are timestamped observations for
trend comparison. Neither is an acceptance constant, and neither authorizes a
write.

Full identifiers to re-read before any runtime verification:

* `280931a8-26f9-41e3-bc18-191f56a2b299` on event
  `d98cdb58-b417-4823-bcc0-119862b165be`
* `ad1c1da7-92c9-4d5b-b378-e8a0bd06cbde` on event
  `135e45b2-0af4-4636-985a-fbfc92e41cc3`
* `c2511a20-0edd-493e-8ff6-9a24040bb55f` on event
  `e2375baf-b28d-449b-9dd9-7f0cc94aeb44`
* `12e942f9-d0eb-4314-90a3-79261bbd0454` on event
  `c1eb5e53-6779-4379-ba2a-95e8ae8e8255`
* `38e5a3f1-fe1c-4a40-b2b5-32923ce0e9fb` on event
  `2b129a98-9179-4700-ad9b-0077dff9f7c8`
* `52076292-ef32-4b6c-abdd-07aae26aad5d` on event
  `afe674e3-332d-475e-86e1-534d97ed687c`
* `de88e547-f9f8-43a9-bc5f-c13d93a6f13e` on event
  `c1eb5e53-6779-4379-ba2a-95e8ae8e8255`
* `14002d16-bed4-4fa3-af8e-e5bac7b91bc1` on event
  `1d776b95-b9fe-4822-aac2-7e067266f88e`

Expected disposition is derived per event state, never as a fixed count. For a
resolved false positive, an active event becomes `confirmed` and an inactive or
deleted single-type event becomes `dismissed`. Rows whose predicate still matches
stay pending while their event is active.

## Predecessor Transfer Summary

The predecessor recount is 99 total checkboxes: 60 complete and 39 incomplete.
Every incomplete item appears once below. Classification totals are:

* Live evidence satisfied but the ledger is unsynchronized: 6
* Waiting for a natural run or external condition: 5
* Executable docs or read-only work: 2
* Tools-only implementation awaiting approval: 9
* Artifact-bound production mutation awaiting approval: 10
* Stale, mutually exclusive, or prerequisite-contradictory: 7

The total is $6 + 5 + 2 + 9 + 10 + 7 = 39$.

## Predecessor Transfer Map

1. `P01` Four-quadrant authorization evidence. Transfer: artifact-bound
   production approval. Status: `APPROVAL REQUIRED` because valid evidence needs
   controlled write attempts.
2. `P02` Workflow and variable state. Transfer: live evidence satisfied. All
   eight allowlisted workflows are active and all three allowlisted variables
   classify as `true` at `2026-08-08T12:53:05Z`.
3. `P03` Lane O natural scheduled run. Transfer: live evidence satisfied.
   Multiple post-G-P.1 scheduled runs have nonzero passing pure-publication
   markers and zero `PGRST204`.
4. `P04` Production apply, runtime acceptance, and reset window pending.
   Transfer: stale historical statement. The bounded outcome is live-verified,
   but its missing snapshot and window transcript remain `INCONCLUSIVE`; do not
   rerun it.
5. `P05` T-P and five G lanes must deploy before T-A. Transfer: contradictory
   prerequisite. T-P is retired, and Lane R superseded only its publication
   reset role. T-A0 may proceed after its own approval without shared extraction.
6. `P06` Extract helpers only for a second consumer. Transfer: tools-only design
   guard. T-A0 imports existing classifiers and extracts nothing.
7. `P07` Implement discover, classify, freeze, apply, rollback, and export.
   Transfer: tools-only implementation split. T-A0 receives only the first,
   second, third, and review-export capabilities; mutation waits for T-A1.
8. `P08` Use full report UUIDs, before-images, and per-field journals. Transfer:
   tools-only mutation contract for T-A1. T-A0 still requires full UUIDs and
   complete read-only before-images.
9. `P09` Add failure injection and rollback rehearsal. Transfer: tools-only T-A1
   validation requirement.
10. `P10` Obtain Tester PASS and tools-only approval. Transfer: tools-only gate.
    No implementation approval exists in this bootstrap.
11. `P11` Verify H0, G1, G4a, and G3 settlement SHAs. Transfer: live evidence
    satisfied. Every claimed SHA resolves and is an `origin/main` ancestor.
12. `P12` Verify G-P clean cycle and Lane R SHA. Transfer: live evidence
    satisfied through release ancestry and nonzero scheduled runtime markers.
13. `P13` Verify inactive maintenance state and auth evidence. Transfer:
    artifact-bound production gate. Inactive row and false RPC are satisfied;
    four-quadrant auth remains `APPROVAL REQUIRED`.
14. `P14` Generate the canonical publication reset snapshot. Transfer: stale
    historical operation. Current evidence is not a replacement artifact, and
    reconstruction is forbidden.
15. `P15` Restrict reset to `error -> pending` and retry zero. Transfer: stale
    historical operation. Lane R code has the contract, but per-row historical
    artifact proof is `INCONCLUSIVE`.
16. `P16` Record observed `updated_at` drift. Transfer: stale historical
    operation. The after-image artifact is unavailable and must not be inferred.
17. `P17` Verify and preflight while writers are disabled. Transfer: stale
    historical sequence. Current state cannot prove the historical ordering.
18. `P18` Release the lock before restoring writers. Transfer: stale historical
    sequence. Current lock false and variables true prove end-state only.
19. `P19` Close the rollback horizon after the first scheduled or GPT write.
    Transfer: live evidence satisfied. Multiple later scheduled writes make the
    historical horizon closed; only fix-forward is valid.
20. `P20` Let the next Error Recovery run settle reports. Transfer: live
    evidence satisfied. Run `30739200907` settled 14 rows on 2026-08-02.
21. `P21` Require separate approvals for reset, lock, workflows, and annotation.
    Transfer: standing artifact-bound production gate for every future window.
22. `P22` Freeze fresh $P_0$ after T-A with two identical scans. Transfer:
    executable read-only task after T-A0. The bootstrap scans are evidence only,
    not the execution ledger.
23. `P23` Verify $P_0=A+S+M$ with one current class per full ID. Transfer:
    executable read-only task after a T-A0 freeze.
24. `P24` Exclude unsafe rows from automatic batches. Transfer: tools-only T-A1
    contract. Compound, human, mixed, unknown, empty, and payload-token rows
    remain in manual routing.
25. `P25` Apply a digest-bound automatic manifest with rollback preview.
    Transfer: artifact-bound production mutation after T-A1 and a frozen ledger.
26. `P26` Deliver evidence-qualified Round S. Transfer: conditional
    artifact-bound source implementation and production apply.
27. `P27` Export manual reports. Transfer: tools-only T-A0 capability; export is
    read-only and digest-bound.
28. `P28` Run final reconcile and scheduled observation. Transfer: waits for an
    approved apply or source repair and its next natural scheduled cycle.
29. `P29` Approve production reset, lock, workflow, migration, settlement, and
    runtime work separately. Transfer: standing artifact-bound production gate.
30. `P30` Approve T-A implementation and validation separately. Transfer:
    tools-only approval gate, beginning with T-A0.
31. `P31` Approve each maintenance lock and writer-state window. Transfer:
    artifact-bound production gate with four-quadrant evidence prerequisite.
32. `P32` Bind every reset to IDs, counts, SHA, command, and restoration.
    Transfer: standing artifact-bound production gate.
33. `P33` Approve final docs archive separately. Transfer: waits for external
    docs-only approval after all closeout criteria pass.
34. `P34` Complete observation for G-P, Lane R, T-A, and conditional Round S.
    Transfer: waits for T-A delivery and any source work proven by the ledger.
35. `P35` Use exact-ID snapshots and literal commands for later applies.
    Transfer: artifact-bound production requirement. The missing historical
    publication artifact is not recreated.
36. `P36` Complete fresh partition and manual export. Transfer: tools-only T-A0
    and post-T-A0 read-only work.
37. `P37` Release and verify the lock before restoring writers in every window.
    Transfer: artifact-bound production invariant.
38. `P38` Complete the final exact scan and natural scheduled cycle. Transfer:
    waits for all approved Admin cleanup actions, not the closed publication
    campaign alone.
39. `P39` Archive the predecessor with `notes.md`. Transfer: waits for all
    closeout checks and a separate docs-only archive approval.

## Phase 0: Successor Review

* [x] Review both successor drafts against the 2026-08-08 evidence
* [x] Confirm the 39-item transfer map and T-P to Lane R decision
* [x] Restructure the drafts around Package A0 and Package A
* [x] Record the 2026-08-09 observation separately from the 179-row baseline
* [x] Retain every full report and event identifier
* [x] Publish the two-path successor draft in `738fd9e8`
* [x] Record the proposal digest
  `1d58638652c2e8caf1117f3b611577f96dec0a101d9c01065fa3d14d7434fc57` and
  task-ledger digest
  `becd6060eaaf45ee34ba8f36b6fcb4f8bc7f61a38ca6796b07c406adf1bed5b2`
* [x] Keep the predecessor three-file hashes unchanged

## Package A0: Time-Critical Exact Repair

### A0.1 Offline `lock_clean` contract tests

* [x] Modify only `scraper/tests/test_qa_auto_fix_unlock_only.py`
* [x] Extend the existing in-memory fake instead of adding a framework
* [x] Prove scalar `expected_event_value` CAS returns exactly one event row
* [x] Prove a list value encodes as `_fc_value()` JSON text, never `repr()` and
  never a comma join
* [x] Prove a scalar value encodes as exact `str(value)` text
* [x] Prove `expected_fc=None` rejects an unexpected row before event mutation
* [x] Prove `expected_event_value` drift rejects before event mutation
* [x] Prove success finalizes the audit row to `applied` with
  `event_after_value_json` set
* [x] Prove a post-write verification failure returns `False`, leaves the applied
  event and correction writes observable, and finalizes `verify_failed`
* [x] Reach no network and no Supabase

### A0.2 Summer Collection `end_date` correction

* [x] Read the exact before-image for event
  `c1eb5e53-6779-4379-ba2a-95e8ae8e8255` read-only
* [x] Confirm no `field_corrections` row exists for `end_date` on that event
* [x] Enumerate all other corrections on that event as preserve-only
* [x] Obtain a separate approval naming the verbatim before-image, the new value
  `2026-08-31T00:00:00+00:00`, `expected_fc=None`, the audit reason digest, and
  `report_id=None`
* [x] Execute exactly one `unlock_and_write(..., mode="lock_clean")` call
* [x] Independently re-read event, `end_date` correction, unrelated corrections,
  and the audit row
* [x] Complete without `False`, ambiguity, or a retry

## Package A: Predicate And Parser Root Cause

### Phase 1 Auto-QA predicates

* [x] Make `start_date IS NULL` the only pure missing-date signal
* [x] Remove `PUBLISH_DATE_SOURCES` after proving it has no remaining consumer
* [x] Preserve `THIN_CONTENT_SOURCES` and its other consumers
* [x] Require local honorific or middle-dot person evidence for missing-performers
* [x] Keep explicit labeled role lists sufficient on their own
* [x] Keep every consumed field in the detector and `reconcile()` projections
* [x] Add projection-aware tests that fail if either projection drops a field
* [x] Test `_check_*()` pure contracts and the detector 30-day window separately
* [x] Preserve and test the `NULL` versus `[]` missing-performer asymmetry
* [x] Assert the three target types are absent from `SAFE_REPORT_TYPES` and
  `HANDLER_MAP`, and that the heartbeat enumerates only `SAFE_REPORT_TYPES`
* [x] Mutate no event or report inside any predicate

### Phase 2 Prospective Eslite parser

* [x] Prefer a labeled top-level event range over publication ISO text
* [x] Prefer a labeled top-level event range over nested item ranges
* [x] Accept weekday tokens and both `～` and `ー` separators
* [x] Keep a one-day labeled event's start and end identical
* [x] Invent no umbrella end when only nested ranges exist
* [x] Claim no repair of already-stored Eslite rows

### Package A validation

* [x] Keep successor docs, A0.1 tests, predicates, and parser in four commits
* [x] Pass 75 focused tests, six-file compilation, the 834-test full suite, and
  the post-build audit in Phase 3
* [x] Complete the write-free Eslite source smoke with 37 events and exit code 0
* [ ] Obtain final independent Tester PASS for the three-commit candidate
* [ ] Obtain explicit approval for the exact three-commit candidate before push
* [ ] Observe the first successful natural run whose head descends from all
  three forward candidate commits
* [x] Re-read the eight named reports and record their actual dispositions
* [x] Record the paginated post-run observation of 173 pending reports, including
  83 `auto_qa_missing_organizer` rows, without authorizing organizer cleanup

### Eslite release and forward hardening

* [x] Publish combined Eslite implementation commit `5c5a6dee`
* [x] Publish the original campaign evidence in `0a1a8c8e`
* [x] Verify one parent, seven direct children, and one inactive redirect
* [x] Verify one authoritative venue, four general-hours events, and four
  preserved event-specific schedules
* [x] Verify 12 field corrections and 12 applied audit rows
* [x] Record summer manifest `4f25dfc756d3` and venue-hours manifest
  `5742d0438ed9` with their verified mutation intervals
* [x] Add direct venue-overlay and one-off-retirement tests in
  `fix(scraper): harden Eslite venue release`
* [x] Align the seven customization files in
  `chore(skills): align Eslite release guidance`
* [x] Complete Phase 3 with 75 focused tests, six-file compilation, 834 passed,
  1 skipped, a passing post-build audit, and a 37-event write-free source smoke
* [x] Observe successful scheduled run `31447829421` covering `5c5a6dee` and
  `0a1a8c8e`, while recording that forward candidate coverage remains pending

## Phase T-A0: Read-Only Tooling

* [ ] Obtain separate tools-only approval bound to the committed successor SHA
* [ ] Modify only `scraper/_oneoff_cleanup_admin_reports.py`
* [ ] Add only `scraper/tests/test_cleanup_admin_reports.py`
* [ ] Implement deterministic exact-count pagination for `discover`
* [ ] Reuse `auto_qa.classify_report_types()` without modifying `auto_qa.py`
* [ ] Require full report UUIDs and complete report and event before-images
* [ ] Require two byte-identical scans before `freeze`
* [ ] Publish ignored mode-`0400` artifacts without overwriting existing paths
* [ ] Export manual, unknown, empty, mixed, compound, and payload-token rows
* [ ] Expose no apply, rollback, settle, reset, lock, GPT, or dispatch command
* [ ] Pass projection-aware fake-client and blocked-network tests
* [ ] Obtain independent Tester PASS
* [ ] Obtain separate commit and push approval

## Phase P0: Frozen Queue Review

* [ ] Reconfirm HEAD, workflow states, variables, lock state, and exact counts
* [ ] Freeze a fresh full-ID ledger from two identical complete scans
* [ ] Verify $P_0=A+S+M$ with one current route per report ID
* [ ] Review every automatic candidate against its current type predicate
* [ ] Produce a digest-bound manual review export
* [ ] Stop on count, digest, projection, type, or before-image drift

## Phase T-A1: Mutation Tooling

* [ ] Draft a separate plan with exact paths, functions, and tests
* [ ] Add per-action manifests with full UUIDs and complete before-images
* [ ] Add status-last writes and observed after-image journals
* [ ] Add failure injection, partial-failure stops, and rollback rehearsal
* [ ] Exclude compound, human, mixed, unknown, empty, and payload-token rows
* [ ] Obtain tools-only approval and independent Tester PASS
* [ ] Perform no production write under a tools-only approval

## Phase D: Production Operations

* [ ] Revalidate the four-quadrant authorization matrix under explicit approval
* [ ] Bind each operation to one existing artifact digest and literal command
* [ ] Capture exact workflow and variable states before changing any writer
* [ ] Disable and drain service-role writers before acquiring the lock
* [ ] Verify lock ownership, writer idleness, and before-image stability
* [ ] Apply only full-ID manifest actions with per-row compare-and-set
* [ ] Verify observed after-images and rollback eligibility before lock release
* [ ] Release the lock and verify inactive before restoring writers
* [ ] Restore exact prior workflow and variable states
* [ ] Treat the first later scheduled or GPT write as the rollback horizon
* [ ] Observe the next natural scheduled cycle without manual dispatch

## Phase S: Conditional Source Repair

* [ ] Start only when the frozen ledger proves a source-owned defect
* [ ] Isolate each source fix, test, deployment, observation, and data manifest
* [ ] Require a separate artifact-bound approval for each source apply
* [ ] Never use source-wide dismissal as a cleanup shortcut

## Verification

* [x] Frontmatter and first-heading assertions pass
* [x] Markdown and prompt diagnostics pass
* [x] UTF-8, EOF newline, whitespace, tab, and conflict-marker checks pass
* [x] `git diff --check` and `git diff --cached --check` pass
* [x] Commit `738fd9e8` contains exactly the two successor files
* [x] Predecessor `proposal.md`, `tasks.md`, and `notes.md` hashes are unchanged
* [x] Worktree path, branch, base, ahead/behind, and status checks pass
* [ ] Lane O baseline mode, size, SHA, byte comparison, and ignore checks pass
* [ ] Main README status, size, and SHA remain unchanged

## Closeout

* [ ] Complete T-A and any evidence-required Round S work
* [ ] Complete all approved manifests and natural scheduled observations
* [ ] Verify no repaired predicate recreates a pending report
* [ ] Produce final exact scan and digest-bound manual export
* [ ] Obtain final docs-only reconciliation and archive approval
* [ ] Preserve predecessor `notes.md` when archiving
