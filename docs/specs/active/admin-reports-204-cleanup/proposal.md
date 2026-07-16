---
slug: admin-reports-204-cleanup
title: Admin Reports 204-Row Cleanup Plan
status: active
branch: feat/admin-reports-204-cleanup
created: 2026-07-12
tags: [scraper, web, data-integrity]
---

## Goal

Reduce the verified production backlog from 204 pending report rows without hiding real defects, then prevent the nightly QA pipeline from recreating resolved rows.

The implementation must fix writers and detectors before changing report status. It must never run the legacy G1 or G3 blanket cleanup scripts.

This revision incorporates `./notes.md` (Round 2 critique): Wave A and Wave B are independent deployment cycles; `confirmReport()` receives only the minimum fail-fast status-last repair in this scope; the single missing-category row and organizer rows without explicit evidence move to manual review instead of expanding parser scope.

## Verified baseline

The read-only production snapshot found:

* 204 pending report rows
* 179 unique events
* 180 Auto-QA rows
* 8 `annotation_error_stuck` rows
* 16 human-submitted report rows
* 25 events referenced by more than one report row
* 2 report rows with multiple `report_types`; both are human compound reports

The current reconciliation result is 1 confirm, 179 keep, and 24 skip. This proves that status-only reconciliation cannot clear the backlog safely.

### Current type distribution

| Report type                                      | Rows |
|--------------------------------------------------|-----:|
| `auto_qa_missing_prefectures`                    |   58 |
| `auto_qa_missing_organizer`                      |   45 |
| `auto_qa_missing_date`                           |   20 |
| `auto_qa_missing_performers`                     |   12 |
| `auto_qa_missing_hours`                          |   11 |
| `auto_qa_missing_address`                        |    9 |
| `auto_qa_missing_location_name`                  |    8 |
| `annotation_error_stuck`                         |    8 |
| `auto_qa_thin_content`                           |    6 |
| `auto_qa_same_work_duplicate`                    |    5 |
| `auto_simplified_chinese`                        |    2 |
| `auto_qa_simplified_zh`                          |    2 |
| `auto_qa_missing_category`                       |    1 |
| `auto_qa_performer_multi_value_pollution`        |    1 |
| Human report rows                                |   16 |
| Total                                            |  204 |

### Immutable discovery ledger artifact

A read-only production query generated the complete 204-row JSONL ledger at:

`/Users/flyingship/Library/Application Support/Code/User/workspaceStorage/6ff2cb1100e61f123c7d4efbbe510f8c/GitHub.copilot-chat/chat-session-resources/7fc23fdb-1e79-4679-94c2-176d10606323/call_CHHlZOpWluEgxJEN8YVPe8cn__vscode-1783097769359/content.txt`

Independent validation returned 204 rows, 204 unique report IDs, 179 unique event IDs, 2 compound rows, and the exact disposition counts below. The normalized 204 JSONL rows have SHA-256 `9a91c63eaf56904580d9a7e08f0b76469e883596b1abe7812b437b49181412e2`.

Engineer must extract the JSONL block, verify the digest, copy it to both protected snapshot locations with mode `0600`, and refuse apply if the digest or production ID set differs. This artifact supplies full UUIDs and source URLs; prefixes in prose are never execution identifiers.

## Exact disposition ledger

The 204 rows have a complete, mutually exclusive accounting. Counts are report rows, not unique events.

| Disposition                              | Rows | Composition |
|------------------------------------------|-----:|-------------|
| Structural or detector false positives  |   58 | 37 core-publication prefecture rows and 21 other structural false positives |
| Deterministic repair                     |   32 | 17 prefecture repairs, 4 simplified aliases on 2 events, 11 other deterministic repairs |
| Source-specific repair                   |   43 | 4 prefecture repairs plus 39 hours, performer, address, location, and organizer repairs |
| Publication date-precision repair        |   20 | NDL rows whose year or year-month metadata was coerced to a false exact date |
| Stale lifecycle reconciliation           |    8 | 4 stale Auto-QA rows and 4 recovered annotation errors |
| Human review                             |   43 | 23 uncertain Auto-QA rows, 4 live annotation errors, 16 human reports |
| Total                                    |  204 | Exact immutable baseline accounting |

The immutable `baseline_disposition` values and JSONL digest remain unchanged. Derive a separate execution manifest from that protected ledger; only its `current_disposition` may change. The Critic-approved execution manifest moves the single missing-category row from deterministic repair to manual review. Therefore Wave A executes 117 baseline IDs and the initial execution-time manual queue contains 44 IDs. Group F organizer rows may move to manual later only after the cycle-2 evidence inventory.

For execution planning, the 98 non-prefecture, non-date, non-simplified Auto-QA rows break down by `current_disposition` as follows. The Deterministic and Human columns show `current_disposition`; within this 98-row subset the corresponding immutable baseline is Deterministic 11 and Human 23, because the single `auto_qa_missing_category` row moved from deterministic repair to manual review.

| Report type                               | Stale | Deterministic | Structural FP | Source repair | Human | Total |
|-------------------------------------------|------:|--------------:|--------------:|--------------:|------:|------:|
| `auto_qa_missing_hours`                   |     0 |             1 |             7 |             3 |     0 |    11 |
| `auto_qa_missing_performers`              |     0 |             2 |             3 |             3 |     4 |    12 |
| `auto_qa_missing_address`                 |     0 |             0 |             1 |             8 |     0 |     9 |
| `auto_qa_missing_location_name`           |     0 |             0 |             3 |             4 |     1 |     8 |
| `auto_qa_thin_content`                    |     0 |             0 |             6 |             0 |     0 |     6 |
| `auto_qa_same_work_duplicate`             |     3 |             2 |             0 |             0 |     0 |     5 |
| `auto_qa_missing_organizer`               |     1 |             4 |             1 |            21 |    18 |    45 |
| `auto_qa_missing_category`                |     0 |             0 |             0 |             0 |     1 |     1 |
| `auto_qa_performer_multi_value_pollution` |     0 |             1 |             0 |             0 |     0 |     1 |
| Total                                     |     4 |            10 |            21 |            39 |    24 |    98 |

## Root causes

### Publication metadata writes physical-field placeholders

[scraper/annotator.py](scraper/annotator.py) and [scraper/_oneoff_backfill_publication_metadata.py](scraper/_oneoff_backfill_publication_metadata.py) write purchase or publication labels into `location_name`, `location_address`, and `business_hours`. Production contains 37 affected core-publication events:

* 27 `ndl_opensearch`
* 10 `hanmoto`
* 37 fake addresses
* 37 fake business hours
* 29 placeholder location names
* 8 unrelated `大阪城ホール` location names
* 8 events with field corrections, including 5 polluted `location_name` locks

A publication has no physical venue. Purchase guidance belongs in descriptions, URLs, or verified price metadata, never in location or hours fields.

### QA predicates are broader than the data semantics

[scraper/auto_qa.py](scraper/auto_qa.py) has these predicate gaps:

* Missing-prefectures omits the publication skip already used by missing-address.
* Missing-date treats every January date outside a broad exemption list as a Contentful placeholder. All 20 current rows are `ndl_opensearch` year or year-month metadata that the scraper coerced to an exact first-of-month date. The report wording is wrong, but the stored precision is also wrong and requires data repair.
* Missing-hours accepts deadlines, article timestamps, update timestamps, and ticket-sale times.
* Missing-performers accepts generic role words even when no person is named.
* Thin-content ignores `parent_event_id`, producing six sub-event false positives.
* Two simplified-Chinese detectors emit aliases for the same event.
* Same-work detection does not execute the location predicate described by its own comments.
* Several report types have no lifecycle-aware reconciliation predicate.

### Backfill is incomplete and parser coverage is narrow

[scraper/backfill_location_prefectures.py](scraper/backfill_location_prefectures.py) performs unpaginated full-table queries. Supabase can cap each response at 1,000 rows, so later events are silently skipped. Its anchored parser also misses labelled strings such as `住所は東京都...`.

The 58 prefecture reports classify as:

* 37 publication pollution rows
* 13 rows already extractable after complete pagination
* 3 rows with short, non-canonical prefecture labels
* 1 bounded prefix-parser gap
* 4 source-specific venue or address defects

### Report lifecycle owners do not close recovered rows

[scraper/error_recovery.py](scraper/error_recovery.py) resets retry counters but does not confirm `annotation_error_stuck` reports after an event becomes `annotated` or `reviewed`. Four of eight rows are already recovered.

[scraper/qa_auto_fix.py](scraper/qa_auto_fix.py) defines a deterministic performer-pollution handler, but its daily `run()` path does not execute that handler. It only runs automatically when QA Heartbeat is live, and the scheduled workflow can remain dry-run when the repository variable is disabled.

### Same-work merger input, detector, and entry points drift

All five current same-work pairs have the same date and overlapping location. Three reports are stale because the counterpart is already inactive or merged. Two active pairs should be handled by merger Pass 5.

The merger's active-event inputs are not fully paginated, so Pass 5 can silently miss pairs beyond the first Supabase page. This is the first root cause to fix. The scheduled [scraper workflow](.github/workflows/scraper.yml) already has a post-annotation merger, but other annotation entry points do not all guarantee this order. After pagination is fixed, the implementation must reproduce both active pairs with a targeted dry-run before changing workflow order. It must not add redundant merger calls to the daily workflow without evidence.

## Scope

### Included

* QA detector and reconciliation predicates
* Publication writer semantics
* Full pagination and bounded address parsing
* Deterministic handler scheduling
* Evidence inventory for all 43 source-specific rows, followed by parser fixes only for the evidence-qualified subset
* One-off, manifest-driven cleanup with rollback snapshots
* Event, field-correction, merge, and report-status verification
* Regression tests and dry-runs

### Excluded

* Changes to the admin reports UI
* Database schema migrations
* Blanket dismissal by category or source
* Automatic organizer guessing
* Broad adoption of OpenCC or cleanup of the entire historical SC-to-TC mapping backlog
* Running `_oneoff_g1_close_safe_reports.py` or either G3 cleanup script
* Unrelated scraper, web, translation, or design-system changes
* A full cross-table compensating-transaction redesign for `confirmReport()`; this plan only makes the existing action fail fast and update report status last
* The Peatix `category=['culture']` writer cleanup; the single current missing-category row moves to manual review, and the writer defect is recorded as a separate follow-up rather than blocking Wave A

No schema change is required.

## Architecture decisions

1. Pure predicates are the source of truth. Detection, deterministic repair eligibility, and reconciliation must call the same helper instead of maintaining parallel rules.
2. Report status changes happen last. An event write, field-correction write, merge, or verification failure leaves the report pending.
3. Every cleanup batch defaults to dry-run and consumes the frozen report-ID manifest produced from a fully paginated query.
4. Nullable field locks use the audited `lock_empty` path with an empty-string `field_corrections.corrected_value` sentinel. SQL NULL is forbidden by the table constraint.
5. List and object locks use JSON text through the existing `_fc_value()` or `_lock_fields_via_corrections()` helpers.
6. Automatic cleanup only handles single-type Auto-QA rows. Any multi-type row is skipped. The two known multi-type rows remain in the human batch.
7. Human reports are never auto-confirmed or auto-dismissed.
8. Fixed venues resolve through `venue_registry` and set `venue_id`. New hardcoded venue-address branches are forbidden.
9. Organizer values must be copied verbatim from source text or structured source metadata. Venue, domain, and publisher guesses are forbidden.
10. Prevention is split into two independent deployment cycles. Group A–E prevention plus the cleanup utility must be validated and deployed before Wave A; Group F source prevention must be validated and deployed only before Wave B. Neither wave may rely on an undeployed writer fix, but unresolved Group F work never blocks Wave A.
11. Every automatic status transition requires `len(report_types) == 1` and an explicit Auto-QA allowlist match. Detection order inside a compound array is irrelevant.
12. Automatic report closure always targets the full `report_id`; event ID plus report type is never sufficient.
13. Human review uses the Admin path only after `confirmReport()` is made fail-fast and status-last. Full cross-table compensation is a separate web-safety follow-up; the Python cleanup utility has no human apply mode.
14. The current missing-category row is manual-only. This plan does not modify the Peatix category writer or broaden category-sync scope for one baseline row.
15. Organizer evidence is quantified before any source parser work. Only rows with explicit `主催` labels or structured organizer metadata enter Group F implementation; all others move directly to the manual queue.

## Affected files

Core files expected to change:

* [scraper/auto_qa.py](scraper/auto_qa.py)
* [scraper/annotator.py](scraper/annotator.py)
* [scraper/_oneoff_backfill_publication_metadata.py](scraper/_oneoff_backfill_publication_metadata.py)
* [scraper/backfill_location_prefectures.py](scraper/backfill_location_prefectures.py)
* [scraper/error_recovery.py](scraper/error_recovery.py)
* [scraper/qa_auto_fix.py](scraper/qa_auto_fix.py)
* [scraper/merger.py](scraper/merger.py)
* [scraper/sources/hanmoto.py](scraper/sources/hanmoto.py)
* [scraper/sources/ndl_opensearch.py](scraper/sources/ndl_opensearch.py)
* [web/app/actions/confirm-report.ts](web/app/actions/confirm-report.ts) — minimum fail-fast, status-last repair only
* A new dry-run-first cleanup utility under `scraper/`
* A separate human-review runbook or review-sheet export under `tmp/`
* New focused tests under `scraper/tests/`

Files that may change only after a reproduction gate:

* [scraper/main.py](scraper/main.py)
* [.github/workflows/annotate-now.yml](.github/workflows/annotate-now.yml)
* [.github/workflows/enrich-and-annotate.yml](.github/workflows/enrich-and-annotate.yml)
* [.github/workflows/error-recovery.yml](.github/workflows/error-recovery.yml)
* [.github/workflows/merger.yml](.github/workflows/merger.yml)

Source-specific files to inspect and change only when the associated source page proves a parser defect:

* [scraper/sources/taiwan_prism.py](scraper/sources/taiwan_prism.py)
* [scraper/sources/acros_fukuoka.py](scraper/sources/acros_fukuoka.py)
* [scraper/sources/livepocket.py](scraper/sources/livepocket.py)
* [scraper/sources/artistcafe.py](scraper/sources/artistcafe.py)
* [scraper/sources/bigromanticrecords.py](scraper/sources/bigromanticrecords.py)
* [scraper/sources/go_taiwan.py](scraper/sources/go_taiwan.py)
* [scraper/sources/nagoya_tcs.py](scraper/sources/nagoya_tcs.py)
* Organizer-capable sources among `kgplus_kyotographie`, `eplus`, `hankyu_hakata`, `kokuchpro`, `nittai_toumonkai`, `doorkeeper`, and `ftip`

## Implementation phases

### Phase 0: Isolate work and freeze the discovery baseline

This phase is sequential and blocks every later phase.

1. Fetch `origin/main` and create a new linked worktree and feature branch. Do not modify the main worktree or the existing `ttr-v8-worktree`.
2. Verify `HEAD == origin/main` in the new worktree.
3. Record `git worktree list`, `git status --porcelain`, and the initial commit SHA.
4. Query all pending report rows using `.range(offset, offset + 999)` until exhausted. Compare `count='exact'` with the accumulated row count.
5. Re-query all referenced events, field corrections, works, merge targets, and same-work counterparts with full pagination. Build an event-to-report index for all 179 unique events and record the 25 events with multiple report rows.
6. Save a discovery bundle under `tmp/qa-report-cleanup/<timestamp>/` and a second private copy outside the worktree. Set file permissions to `0600` and record SHA-256 digests. This is the historical 204-row baseline, not the later apply snapshot.
7. Produce the immutable 204-ID ledger before implementation. Each row must contain the full `report_id`, full `event_id`, ordered `report_types`, `baseline_disposition`, initial `current_disposition`, batch, action, target status, predicate owner, exact field updates, FC lock mode, evidence URL, and both full merge UUIDs when applicable. Hash and protect this artifact; never edit it afterward.
8. Derive a separate execution manifest keyed by the same 204 report IDs. Apply the Critic-approved reclassification there: move the single missing-category row to `current_disposition=manual` before any batch planning. Later evidence triage may update only this execution manifest, with an append-only change log that records old/new disposition, reason, timestamp, and evidence URL.
9. Assert that the pending-ID set exactly equals both ID sets, each artifact has 204 rows and 204 unique report IDs, every immutable row has one baseline disposition, and every compound row is `manual_only` in the execution manifest.
10. Stop if the total is not 204, the type set changed, an ID is absent, or a report is assigned more than once. Reclassify the fresh delta before continuing.

### Phase 1: Add regression tests before production logic changes

This phase is sequential. Later prevention groups can proceed in parallel after these failing fixtures exist.

Add focused tests for:

* Publication events never receiving physical location or business-hour placeholders
* Missing-prefectures skipping true publications but not physical book launches
* A legitimate January event and an NDL year-precision value following their source-specific precision policy rather than a blanket Contentful rule
* The existing Tokyo Art Beat health-check and auto-fix owners still detecting and repairing documented Contentful slug/date mismatches, without duplicating that logic in Auto-QA
* Deadlines, publication timestamps, article update times, and ticket-sale times not counting as event hours
* A labelled event time counting as event hours
* Generic performer role words not creating reports without a named person
* A named performer candidate creating a report or deterministic repair candidate
* Child events with usable parent context not being marked thin
* Simplified aliases producing one canonical finding while legacy aliases remain reconcilable
* Same-work merge eligibility using one shared date and location predicate
* Same-work candidates and active merger inputs beyond row 1,000 remaining visible
* Annotation-error reports closing only after `annotated` or `reviewed`
* Multi-type and human reports in both `[auto,human]` and `[human,auto]` order never being auto-closed
* Full pagination beyond 1,000 rows in every merger pass, including orphan children, parents, grandchildren, and siblings
* No active child whose parent is inactive after paginated merge cleanup
* Bounded address prefixes such as `住所は東京都...` without broad substring false positives
* `大阪府大阪市住之江区新北島...` resolving to `大阪府`, not Taiwan's `新北`
* Official Japanese prefecture forms and the Tokyo versus Kyoto substring trap
* `lock_empty` writing the empty-string sentinel, never SQL NULL

### Phase 2: Prevent recurrence

After Phase 1, Group A through Group E form **deployment cycle 1** and may run in parallel; they must integrate before Wave A. Group F forms **deployment cycle 2** and starts only after Wave A passes its own nightly observation gate. Group F is not a dependency of Wave A and must never delay the 117-row high-value cleanup.

#### Group A: Correct publication semantics

1. Define one narrow `is_core_nonphysical_publication()` helper for `ndl_opensearch` and `hanmoto`. Do not classify a row as nonphysical from `books_media` or `event_form=publication` alone because book launches can have real venues.
2. Extract the core-publication update construction into one shared helper used by the annotator and the historical publication backfill.
3. Fix the Hanmoto source writer itself: unknown `price_info` and `business_hours` remain null rather than receiving purchase placeholders.
4. Keep `event_form=['publication']`, verified descriptions, source URLs, publisher organizer data, and verified numeric price metadata.
5. Keep `location_name*`, `location_address*`, and `business_hours*` empty for core nonphysical publication rows.
6. Do not turn purchase guidance into physical venue, address, hours, or price text.
7. Respect all human-protected fields. Do not directly overwrite field corrections.
8. Make missing-prefectures call the same narrow core-publication skip used by missing-address.
9. Paginate the historical backfill's candidate and FC queries, or require explicit event IDs for apply mode.

#### Group B: Narrow and unify QA predicates

1. Replace the blanket January rule with a positive source-precision policy. Do not duplicate Tokyo Art Beat URL/date mismatch logic already owned by health-check and QA auto-fix.
2. Change NDL parsing so only `YYYY-MM-DD` creates an exact `start_date` and `end_date`. For `YYYY` or `YYYY-MM`, keep the date null and preserve the source precision in generated publication descriptions without rewriting `raw_description`.
3. Make missing-date accept null for core publications whose source precision is insufficient. A future exact date requires an explicit precision schema and UI change, which is out of scope.
4. Make missing-hours require event-time context and reject deadline, sales, publication, article, and update contexts.
5. Reuse the conservative annotator hours extractor where possible.
6. Make missing-performers require at least one conservative named-person candidate. Generic role words alone are not actionable.
7. Skip thin-content reports for sub-events that have sufficient structured fields or usable parent context.
8. Make `auto_simplified_chinese` the only newly emitted type. Its canonical predicate scans the fixer's six Chinese fields plus `selection_reason.zh`, uses `SC_ONLY`, and requires at least two hits.
9. Keep `auto_qa_simplified_zh` as reconciliation-only legacy alias until the backlog is closed. Generate `SIMP_RE` from the canonical set or remove it as an independent definition.
10. Assert `SC_ONLY` is a subset of `_SIMP_TO_TRAD_RAW` mappings. Before confirming a repair, verify every detected character changed or is mapped. An affected field with a human FC moves to manual review rather than being overwritten.
11. Add narrow no-venue and overseas checks only when backed by explicit event signals. Do not suppress all `books_media` events.
12. Create a shared `is_single_type_auto_report()` guard and require it in reconciliation, simplified handling, performer handling, annotation-error handling, and cleanup orchestration.
13. Remove the generic `reviewed` shortcut from Auto-QA reconciliation. Every type except recovered annotation errors must re-run its own predicate before closure.

#### Group C: Repair prefecture extraction infrastructure

1. Introduce a reusable fully paginated fetch helper in the prefecture backfill.
2. Compare first-page count, exact count, and accumulated count in logs.
3. Accept bounded labels such as `住所は`, `所在地`, and `会場住所` before a formal prefecture.
4. Parse a Japanese prefecture before checking Taiwan aliases. Taiwan administrative names must occur at the normalized address start or include the full `市` or `縣` suffix, preventing `新北島` from matching `新北`.
5. Do not use unrestricted searches that can mistake prose, organizer addresses, or Taiwan locations for a Japanese event venue.
6. Keep values in full Japanese form, such as `東京都`, `京都府`, and `神奈川県`.
7. Treat the three existing short-label rows as a one-off data repair, not a new permanent cron stage, unless a current writer is proven to emit them.

#### Group D: Close lifecycle gaps

1. Fully paginate every event input used by merger Passes 0 through 5, including Pass 3 orphan children and parent lookups plus Pass 4 grandchildren, roots, and sibling lookups. Log first-page, exact, and accumulated counts before diagnosing workflow order.
2. Add a shared same-work news-pair eligibility helper in the merger and reuse it from detector and reconciliation code. Preserve the existing date and location truth table; the two current target pairs must have non-null matching dates and overlapping locations.
3. Reconcile same-work reports by querying current active candidates with the same `work_id`; never parse an eight-character UUID prefix from report text.
4. Reproduce the two active pairs with a targeted merger dry-run after pagination. Do not run unrestricted live merger from the cleanup utility because it could change rows outside the manifest.
5. If scheduled merger handles the pairs, let the deployed flow merge them and reconcile their reports against the fresh apply baseline. If targeted apply is necessary, invoke a shared merge primitive with both full manifest UUIDs.
6. Only after pagination and reproduction, add a post-annotation merger to entry points that demonstrably omit it. Audit the daily scraper workflow, merger workflow, annotate-now, enrich-and-annotate, and error-recovery paths. Do not duplicate an existing post-annotation pass.
7. Verify that every merge sets `is_active=false` and `merged_into_event_id`, preserves the canonical active target, updates reports by full report ID, and creates no redirect cycle. A merged secondary report is confirmed; a merely deactivated unmerged report is dismissed. Require zero active children whose parent is inactive after Pass 3, and add a >1,000-row orphan/grandchild regression fixture.
8. Add annotation-error reconciliation to the error-recovery owner. Settle both `annotated` and `reviewed` events, reset retry count, and confirm only a single-type `annotation_error_stuck` row.
9. Add a lightweight `--reconcile-only` mode after annotation. Verify `ERROR_RECOVERY_LIVE=true` and a recent successful workflow; otherwise run reconciliation from the known-live daily path.
10. Treat success status, retry reset, and report confirmation as one all-or-compensate item. Compound rows and human report types remain unchanged.

#### Group E: Make deterministic handlers and human review status-last

1. Extend the daily `qa_auto_fix.run()` path to process the performer multi-value handler without GPT and without depending on `QA_HEARTBEAT_LIVE`.
2. Keep the existing audit trail and `lock_empty` sentinel behavior.
3. Do not add organizer guessing or broad location search to this deterministic path.
4. Reclassify the single `auto_qa_missing_category` row as manual-only before implementation. Do not modify the Peatix category writer in this plan; record that writer defect as a separate follow-up and do not let it block Wave A.
5. Apply the minimum `confirmReport()` safety repair: check and return every existing event/correction write error, then move the `event_reports.status='confirmed'` update after all existing writes. Any earlier failure returns an error while the report remains pending. Because this reduced action still sets a single per-row status, it cannot close one type of a compound row while leaving the other pending; the two compound rows are therefore handled through the existing manual Admin branch and are never closed by this action, and per-type partial close stays within the separate cross-table compensation follow-up.
6. Do not add a manual cross-table compensation protocol, new before-image machinery, or new correction-table semantics in this plan. Track those as a separate web-safety follow-up; this cleanup only requires fail-fast status-last behavior.
7. Run the category synchronization guard because `annotator.py` is touched. Verify `VALID_CATEGORIES`, the annotator prompt, all three message catalogs, and both admin API prompts remain aligned. No category enum is added and no message file should change.

#### Group F: Quantify evidence, then fix only proven source writers

This group belongs to deployment cycle 2 and cannot start until Wave A completes its nightly observation gate.

1. Reference each of the 43 source-specific baseline rows in the execution manifest, binding one full report ID, full event ID, source file, source evidence, expected field output, and regression fixture. The immutable discovery ledger was frozen in Phase 0 and is never edited here; regression fixtures and evidence are recorded only in the execution manifest.
2. Before changing any organizer parser, run a read-only evidence inventory for the 21 organizer rows using the ledger's full event IDs. Export `raw_title`, `raw_description`, source URL, structured source payload when available, and the exact evidence span. Let `N` be the rows with an explicit `主催` label or structured organizer field; let `o_manual = 21 - N`.
3. Update only the execution manifest before implementation: the `N` proven organizer rows retain `current_disposition=source_repair`; all `o_manual` rows become `manual` with a reason and evidence URL in the append-only change log. The immutable discovery ledger remains untouched. Do not inspect or modify parser code for a source whose only baseline rows moved to manual.
4. Fix the four prefecture owners, including JATS room or campus addresses, IWAFU's Nishinomiya address, and `go_taiwan` venue versus address parsing.
5. Fix the eight address owners through explicit page fields, parent-room inheritance, or authoritative venue lookup. No generic web-search value is written without source verification.
6. Fix the four `go_taiwan` missing-location child rows at the splitting boundary. Keep overseas address QA non-applicable where appropriate, reject venue names such as `甲子園球場` as addresses, and use UTC midnight dates.
7. Fix hours extraction in `taiwan_prism`, `acros_fukuoka`, and `livepocket`, preserving programme-level schedules rather than one arbitrary time.
8. Fix the three structured performer owners, including programme, exhibitor, and stage-cast formats. Do not populate `performers[]` from generic group labels.
9. For the `N` proven organizer rows only, inspect and modify the owning source among `kgplus_kyotographie`, `bigromanticrecords`, `acros_fukuoka`, `go_taiwan`, `peatix`, `eplus`, `hankyu_hakata`, `kokuchpro`, `nittai_toumonkai`, `doorkeeper`, and `ftip`. Copy the organizer verbatim; filter non-event `nittai_toumonkai` rows instead of inventing organizers.
10. If evidence for any other source-specific row is unavailable or contradictory, increment `b_manual`, set `current_disposition=manual`, and skip that parser change.
11. Run source dry-runs only for sources actually modified and verify exact target rows after re-scrape without writing unrelated event changes.

### Phase 3: Deployment cycle 1 — validate and deploy Group A–E

This phase is sequential and gates Wave A only. Group F is explicitly out of scope for this deployment cycle.

1. Complete Group A–E and the dry-run-first cleanup utility. No Group F source parser is required before Wave A.
2. Run the focused tests, the complete scraper test suite, and web checks for the minimum `confirmReport()` fail-fast/status-last repair.
3. Run Python syntax checks for every changed scraper module.
4. Run prefecture, Auto-QA reconciliation, QA auto-fix, targeted merger, and annotation-error dry-runs.
5. Run source dry-runs for Hanmoto, NDL, and every Group A–E source actually modified. Peatix is excluded from cycle 1.
6. Verify no files under `web/messages/` changed.
7. Verify no database migration or schema operation is present.
8. Split cycle-1 prevention into reviewable atomic commits: QA predicates, publication writers, prefecture and merger pagination, lifecycle and deterministic handlers, minimum Admin status-last safety, and cleanup utility. Do not include Group F source parser commits.
9. Include generalized lessons in the corresponding fix commit rather than creating a second documentation-only deployment cycle.
10. Have Tester return PASS before asking for push approval.
11. Push and verify all cycle-1 workflow revisions and live-variable prerequisites before Wave A production cleanup.

### Phase 4: Freeze the Wave A apply baseline after cycle-1 deployment

This phase is sequential and blocks all Wave A writes.

1. Confirm no related scraper, merger, error-recovery, QA auto-fix, reconciliation, or scan workflow is running.
2. Re-fetch all original 204 report IDs and classify them as still pending, naturally resolved by cycle-1 prevention, reserved for cycle 2, manual-only, or unexpected drift.
3. Build the Wave A apply snapshot from only the still-pending original IDs assigned to A1, A2, or A3. Group F and manual IDs remain frozen but are not writable in this snapshot. Newly created legitimate reports are tracked separately and never folded into the historical denominator.
4. Group pending Wave A rows by event ID. The mutation unit is one event, not one report row. Compose all compatible event and FC changes for that event into one expected after-image; detect cross-batch dependencies before assigning execution order.
5. Store full before-images and expected after-images for every touched event, FC, report, merge primary, and merge secondary. Include venue-derived fields `venue_id`, `location_url`, `latitude`, and `longitude` for publication cleanup.
6. For any event that must change in multiple Wave A sub-batches, generate and hash a chained intermediate snapshot after each verified event-level mutation. Never reuse the discovery before-image after the event has changed.
7. Verify both protected snapshot copies and their SHA-256 digests, then record the cycle-1 deployed commit SHA.
8. Re-run the 204-ID uniqueness, single-type, human, compound, event-group, and batch-scope guards. Any Group F or manual ID in the Wave A apply set is a hard stop. Unexpected drift requires ledger reconciliation.

### Phase 5: Wave A cleanup for 117 baseline rows

This wave is sequential by sub-batch. Counts refer to original baseline rows; rows already resolved naturally after prevention are verified and reconciled rather than rewritten. For each event group, compose and verify event plus FC changes once, then close each eligible single-type report by full ID after its own predicate passes.

#### Batch A1: Structural false positives and publication precision, 78 rows

* Repair 37 core-publication events first. Clear physical location and hours fields, set `location_prefectures=[]`, clear pollution-derived venue ID, URL, and coordinates where the snapshot proves they came only from the fake venue, remove exact placeholder-only price text, and replace polluted locks with audited values. Scalar null locks use `""`; `location_prefectures` uses JSON `"[]"`. Preserve verified descriptions, publisher organizer fields, URLs, and real prices.
* Close the 37 publication reports only after the corrected publication predicate returns no finding.
* Repair the 20 NDL date-precision rows. Replace exact dates created from `YYYY` or `YYYY-MM` metadata with null dates, preserve the source precision in publication descriptions, and protect the repaired fields through the audited path. Confirm only after the core-publication precision predicate passes.
* Dismiss the other 21 structural false positives with a reason specific to each detector: 7 hours, 3 performers, 1 overseas address, 3 no-single-location rows, 6 parent-context thin rows, and 1 no-single-organizer row.

#### Batch A2: Deterministic repairs, 31 rows

* Repair 17 prefecture rows: 13 currently extractable rows, 3 short-label normalizations, and 1 bounded prefix-parser case.
* Convert and lock the two simplified events once, then confirm all four alias report rows.
* Apply the 10 remaining deterministic repairs: 1 hours, 2 performers, 2 same-work merges, 4 organizers copied from explicit source metadata, and 1 performer split. The missing-category row is not part of A2 and remains manual-only.
* For the two same-work merges, use the targeted shared merge primitive with both full UUIDs. Never invoke unrestricted live `merger.py` from the cleanup utility. Verify no merge cycle and no active merged secondary remains.

#### Batch A3: Stale reconciliation, 8 rows

* Confirm 3 same-work rows with no current active candidate.
* Confirm 1 missing-organizer row whose organizer now exists.
* Confirm 4 annotation-error rows whose events are already `annotated` or `reviewed`.

Wave A completion gate:

* All 117 Wave A baseline IDs are either naturally resolved by deployed prevention or changed through a verified manifest action.
* No Group F, human, or compound report changed.
* Every repaired event passes its current predicate.
* Let `a_manual` be any Wave A row moved to manual because its evidence failed the apply gate. Expected unresolved original-baseline rows become `87 + a_manual` (43 cycle-2 rows + 44 baseline manual rows + `a_manual`).
* Complete one nightly scraper, merger, reconciliation, and Auto-QA cycle now. Any regenerated Wave A type blocks deployment cycle 2 and returns to its owning Group A–E prevention work.

### Phase 6: Deployment cycle 2 and Wave B source-specific repair for 43 baseline rows

This phase starts only after the Wave A nightly observation gate passes. It combines Group F evidence triage, a separate source-parser deployment, a fresh Wave B apply snapshot, and then targeted cleanup.

Deployment cycle 2 gate:

1. Complete the Group F evidence inventory first. Record `N`, `o_manual = 21 - N`, and every other evidence failure in the execution manifest and its append-only change log before editing source parsers; do not alter the immutable discovery ledger.
2. Implement parser fixes only for rows that remain `current_disposition=source_repair`. Sources whose baseline rows all moved to manual are not modified.
3. Add a focused fixture and run `main.py --dry-run --source <source>` for every source actually changed; run the scraper test suite and Python syntax checks.
4. Have Tester return PASS, obtain push approval, deploy only the reviewed Group F commits, and verify the deployed commit SHA. Cycle-1 Group A–E code remains unchanged.
5. Confirm no related workflow is running, then build a new Wave B apply snapshot from still-pending original IDs assigned to Group F. Record complete event/FC/report before-images and expected after-images; exclude Wave A and manual IDs.
6. Re-run the single-type, human, compound, event-group, source-evidence, and batch-scope guards. Any non-Group-F ID in the Wave B apply set is a hard stop.
7. Apply targeted re-scrapes or audited patches in parallel by independent source, integrate sequentially, and close only reports whose shared predicate no longer fires.

#### Venue and region group, 16 rows

* Repair 4 prefecture source defects.
* Repair 8 missing addresses through source parsers, parent-room inheritance, or authoritative venue registry data.
* Repair 4 missing locations caused by `go_taiwan` child-event splitting.
* Ensure `go_taiwan` does not treat `甲子園球場` as an address and writes UTC midnight dates rather than JST-aware midnights.
* Use `venue_registry` for shared fixed venues and set `venue_id` on a hit.

#### Event metadata group, 27 baseline rows

* Repair 3 event-hour parsers in `taiwan_prism`, `acros_fukuoka`, and `livepocket`.
* Repair 3 performer-list parsers, including programme, exhibitor, and stage-cast formats.
* Of the 21 organizer rows, repair only the evidence-qualified `N`; move `o_manual = 21 - N` directly to manual review before parser implementation.
* Copy organizer names only from explicit labels or structured source metadata.
* Filter non-event `nittai_toumonkai` rows instead of inventing organizers.

For each source:

1. Capture the original page or API evidence in the cleanup manifest.
2. Add a regression fixture.
3. Run `main.py --dry-run --source <source>`.
4. Apply a targeted re-scrape or audited event patch.
5. Re-read event and field-correction rows.
6. Close only reports whose shared predicate no longer fires.

Wave B completion gate:

* Let `o_manual = 21 - N` be organizer rows triaged to manual before parser implementation. Let `b_manual` be evidence failures among the other 22 source-specific rows or among rows initially counted in `N` whose source later contradicts the proposed repair.
* Exactly `43 - o_manual - b_manual` Wave B baseline rows are resolved; all `o_manual + b_manual` rows move to the manual queue with reason and evidence recorded.
* Expected unresolved original-baseline rows become `44 + a_manual + o_manual + b_manual`.
* No missing organizer is guessed from venue, domain, or publisher identity, and no parser is modified for a source with no evidence-qualified baseline row.

### Phase 7: Export the human review queue

No row in this phase is eligible for Python apply or automatic closure. The cleanup utility only exports a review sheet. Human decisions are performed one by one through the fail-fast, status-last Admin action. The baseline manual queue contains 44 rows; add `a_manual + o_manual + b_manual` rows dynamically after the two automatic cycles.

#### Uncertain Auto-QA, 24 baseline rows

* Review 18 missing-organizer rows against the original page.
* Review 4 missing-performer rows where the available text names only generic groups or incomplete rosters.
* Review 1 Doorkeeper missing-location row to determine online versus physical delivery.
* Review the single `auto_qa_missing_category` row manually using source evidence. Do not modify the Peatix parser as part of this cleanup; record the writer defect as a separate follow-up.

#### Live annotation errors, 4 rows

* Export full UUIDs from the immutable ledger for all four rows; prefixes below are display hints only.
* Deactivate `9c39e40b` if the original note page remains a pure book review rather than an event.
* Decide whether `9b48806d` is an ended recap, a mixed article requiring future sub-events, or out of scope.
* Repair `7bd4658c` from its complete Kofu source page, including date, venue, address, and performers.
* Decide whether `a7571bb7` is a valid streaming or broadcast event; otherwise deactivate it.
* For each row, the review sheet specifies target report status, deactivation audit fields, exact FC policy, and evidence URL.

#### Human reports, 16 rows

* Review 12 wrong-category rows individually.
* Review 2 irrelevant rows; confirming irrelevance must also deactivate the event with an explicit reason.
* Review the wrong-selection-reason compound row without closing its other type prematurely.
* Review the wrong-details and date compound row in one Admin decision without closing either type prematurely.

All manual field corrections must be locked in `field_corrections`. Address changes must update and lock `location_prefectures` before the report status changes. Reviewed events must retain non-null `name_zh` and `name_en`. Full cross-table compensation remains a separate web-safety follow-up and is not claimed by this cleanup plan.

### Phase 8: Reconcile, rescan, and observe one nightly cycle

This phase is sequential and is the final whole-plan observation after both deployment cycles and all completed Admin decisions. Wave A already had its own nightly gate before cycle 2.

1. Run Auto-QA reconciliation in dry-run and confirm that its proposed changes contain no human report.
2. Apply reconciliation.
3. Run a fresh Auto-QA scan with the corrected code.
4. Query all pending rows again with full pagination and exact count.
5. Compare the new queue against the immutable discovery baseline plus the separate Wave A and Wave B apply snapshots by report ID, event ID, and type.
6. Assert that resolved publication, January-date, thin-child, duplicate-simplified, stale-annotation, and source-specific rows did not regenerate.
7. Assert no active event has both `merged_into_event_id IS NOT NULL` and `is_active=true`.
8. Run the merge-cycle detector and require zero cycles.
9. Wait for one scheduled nightly scraper, merger, reconciliation, and Auto-QA cycle.
10. Repeat the exact-count query. Any regenerated baseline type blocks completion and returns to its owning Group A–F prevention work.

The baseline arithmetic is dynamic: after Wave A, unresolved original rows are `87 + a_manual`; after Wave B, they are `44 + a_manual + o_manual + b_manual`; after Admin completes every exported decision, the original baseline reaches zero. New legitimate reports are reported separately and never hidden to satisfy the historical target.

## Cleanup utility requirements

Create one dry-run-first utility with these properties:

* `--manifest <path>` is mandatory for apply mode and must point to the frozen Wave A or Wave B execution manifest derived from the immutable discovery ledger.
* Apply verifies that the immutable discovery-ledger digest still matches the recorded SHA-256; it never edits that ledger.
* `--batch A1|A2|A3|B` limits automatic scope.
* `--export-review-sheet C` exports the manual queue and cannot write production data.
* `--apply` enables writes; absence means dry-run.
* `--rollback <snapshot>` restores only rows whose current complete values equal the recorded expected after-image.
* Every query paginates completely.
* Apply mode asserts the deployed commit SHA recorded in the matching Wave A or Wave B apply snapshot, report status, ordered report types, event touched fields and `updated_at`, complete FC row state, and merge before-image before each write.
* Reuse and strengthen `unlock_and_write()` and the existing QA audit/rollback infrastructure. Do not build a second FC serializer or audit protocol.
* Group report rows by event ID within the selected wave. Compose all compatible automatic mutations into one event/FC expected after-image, apply and verify once, then close each qualifying report individually by full report ID. If an event appears in both waves, Wave B must snapshot the post-Wave-A state rather than reuse the discovery before-image.
* Because no migration is planned, each event group is all-or-compensate rather than a claimed cross-table transaction. Write and verify the FC/audit state, update and verify the event, then update reports last. Any failure restores completed steps from the current chained before-image and verifies compensation.
* A partial failure stops the current batch and leaves all unverified reports pending.
* Report notes record batch, disposition, source evidence, deployed commit SHA, and timestamp.
* The utility refuses human types in A or B and refuses compound rows in all automatic batches.
* Merge snapshots include the primary's `raw_description`, `annotation_status`, and `secondary_source_urls`; and the secondary's `is_active`, `merged_into_event_id`, `deactivated_at`, `deactivated_reason`, and `deactivated_by_pass`.
* Publication snapshots additionally include `venue_id`, `location_url`, `latitude`, and `longitude`.
* Rollback restores event fields, FC rows, report state, and merge state only after complete after-image comparison.

## Verification commands and checks

Engineer must use the configured workspace Python environment and run these checks from the isolated worktree:

```bash
python -m pytest scraper/tests
python -m compileall -q scraper
cd scraper && python backfill_location_prefectures.py --dry-run
cd scraper && python merger.py --dry-run
cd scraper && python auto_qa.py --reconcile --dry-run
cd scraper && python auto_qa.py --dry-run
cd scraper && python qa_auto_fix.py --dry-run
cd scraper && python error_recovery.py --dry-run --limit 100
```

For every modified source:

```bash
cd scraper && python main.py --dry-run --source <source_name>
```

Production read-only verification must prove:

* accumulated paginated count equals `count='exact'`
* every baseline report ID has exactly one disposition
* the Wave A apply set contains exactly A1/A2/A3 IDs and no Group F/manual IDs; the Wave B apply set contains only evidence-qualified Group F IDs
* no automatic batch contains a human or compound report
* organizer evidence inventory records `N`, `o_manual = 21 - N`, and an exact source span for every row retained for parser repair
* the single missing-category row remains manual-only and no Peatix parser or message catalog change is included
* `confirmReport()` returns on every existing write error and performs its report-status update last; no test or documentation claims full cross-table compensation
* no fixed event still triggers its shared predicate
* simplified detection and repair scan the same fields
* all detected simplified characters in the two current events are mapped and converted
* no short Japanese prefecture labels remain on active events
* Japanese `新北島` addresses do not take the Taiwan branch
* no core publication event contains purchase guidance in location or hours fields
* NDL year or year-month metadata is not represented as a false exact date
* no inactive merged event remains active
* no active child has an inactive parent after merger cleanup
* no merge cycle exists
* all reviewed events retain Chinese and English names
* no changes exist under `web/messages/`

## Rollback and stop conditions

Stop immediately when any of these conditions occurs:

* HEAD or production counts drift before apply
* an unexpected report type appears in the manifest
* an event, FC row, merge participant, or report differs from its recorded before-image
* a source page contradicts the proposed repair
* any FC, event, audit, or compensation verification fails
* a report would close while its predicate still fires
* a merge target is inactive, cross-work, or creates a cycle
* any automatic batch reaches a human or compound report
* Tester returns FAIL

Rollback must use the frozen snapshot and audit records. Do not use broad reverse updates, old one-off scripts, or report-type-wide status changes.

## Definition of done

* Group A–E prevention and the cleanup utility are deployed before Wave A; Group F prevention is independently evidence-scoped, tested, and deployed only before Wave B.
* Wave A completes its own nightly observation before Group F implementation begins.
* The immutable 204-ID ledger plus separate Wave A and Wave B apply snapshots pass hash, scope, and uniqueness verification.
* Wave A and Wave B have exact before and after ledgers using the dynamic `a_manual`, `o_manual`, and `b_manual` counts.
* The baseline 44-row human queue plus all dynamically reclassified rows is exported with full UUIDs, evidence, and exact decisions; no Python apply path can close it.
* The missing-category row stays manual-only; Peatix category cleanup and full `confirmReport()` compensation remain separately tracked follow-ups.
* All event changes are verified and protected where required.
* Admin decisions use the minimum fail-fast, status-last action and produce explicit individual outcomes.
* A fresh scan and the relevant nightly observation do not recreate resolved baseline rows after either deployment cycle.
* Tester returns PASS for each deployment cycle's modified scraper, web action, and workflow paths.
* Each push occurs only after explicit user approval.
