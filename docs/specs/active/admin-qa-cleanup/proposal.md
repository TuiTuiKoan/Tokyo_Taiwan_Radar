---
slug: admin-qa-cleanup
title: Admin QA Cleanup Successor
description: Rebaseline and execution gates for the remaining Admin Reports QA cleanup
status: active
branch: feat/admin-qa-cleanup
created: 2026-08-08
tags: [scraper, tooling]
---

## What

Continue the unfinished Admin Reports QA cleanup from a live, read-only
rebaseline. This successor is the execution tracker for future work. The
predecessor at `docs/specs/active/admin-reports-204-cleanup/` remains immutable
audit history until a separate final archive approval.

Delivery runs as two ordered packages. Package A0 is the time-critical
correction: offline `lock_clean` contract coverage first, then a separately
approved single-field `end_date` repair for the still-running eslite Collection
event. Package A is the root-cause implementation: refresh this successor, repair
the missing-date and missing-performer predicates, repair Eslite date-range
parsing prospectively, validate, and release through the normal cycle.

The tools-only track named T-A0 remains a later, approval-bound slice. It can
discover, classify, freeze, and export the pending queue, but it cannot write to
Supabase. Apply, rollback, source repair, maintenance windows, and report
settlement stay behind their own approvals.

## Why

The predecessor mixes delivered work with stale future-tense instructions. Its
99 checkboxes recount as 60 complete and 39 incomplete, but several incomplete
items describe work that has since run in production. Other items still require
code, immutable artifacts, or explicit production approval.

The live queue also drifted from the predecessor's 2026-07-29 observation of 174
pending rows. On 2026-08-08, two complete scans found 179 pending rows across 154
events. Historical counts are comparison points only and never authorize an
apply.

Investigating the named rows showed that most are predicate faults, not data
faults. The missing-date predicate treats any January `start_date` as a
Contentful placeholder, so a genuinely valid January event stays flagged forever.
The missing-performer predicate matches a role word and a personal-name pattern
independently anywhere in the text, so a generic role word combined with an
unrelated Katakana subtitle elsewhere on the page produces a false positive. One
real data defect is time-critical: eslite Collection -夏日の奇幻旅程- stores a
truncated `end_date`, so a still-running event is presented as ended.

## Evidence Baseline

### Repository and release state

The Git preflight completed at `2026-08-08T12:45:36Z`. The canonical worktree is
on `feat/admin-qa-cleanup` at
`5d6e4a43ccf226da7c9a5c5b6e1dfc5dcaec6b26`, equal to `origin/main`, with
ahead/behind `0/0` and no operation in progress.

Every predecessor delivery reference resolved uniquely and is an
`origin/main` ancestor: publication-policy `feb530e`, H0 `5457b5f2`, G1
`a2ba5bbe`, G2 `796aa7f8` and `56e677e2`, G3 `77741cd5` and `e8552682`, G4a
`60978b5c` through `1295ca4d`, G4b `e6203c09`, `6b739a42`, `90e5e9fd`, and
`c7f42c4c`, G-P `7c98491b8f7efd60d03c2b6d21112aca5a20389f`, G-P.1
`085d4441edf9a12eeb4ec774b84f900649f08302`, and Lane R
`fadbe289cb57d49f018d00cc22db0c5bdd87729d`.

### Lane O and publication closeout

GitHub evidence was observed at `2026-08-08T12:53:05Z`. The scheduled Daily
Scraper query used `event=schedule`, `created>=2026-07-31`, and `per_page=100`.
It returned exact count 9, fetched 9, and was pagination-complete. Eight
successful runs used a head SHA containing exact G-P.1.

The natural scheduled run `30678924406` on
`fadbe289cb57d49f018d00cc22db0c5bdd87729d` emitted one pure-publication
finalizer marker. Its aggregate evidence was
`internal_key_consumed=true`, `publisher_evidence_present=true`, zero
`internal_key_consumed=false`, zero `PGRST204`, and zero raw internal-key
tokens. Later natural runs repeated the nonzero path. For example, run
`31140232664` emitted one passing pure marker, and runs `30967185465` and
`31063495635` emitted 11 and 8 passing pure markers.

Scheduled Error Recovery run `30691105418` on 2026-08-01 scanned 18 errors,
including 14 `ndl_opensearch` escalations. Run `30739200907` on 2026-08-02
settled 14 recovered escalations. Run `30801513896` on 2026-08-03 then reported
zero scanned and zero settled. Current live evidence independently shows zero
active annotation errors and zero pending `annotation_error_stuck` reports.

The outcome and runtime path are verified. The original full-ID reset snapshot,
window-state capture, and observed physical after-image are not present in the
checked-in repository or preserved local artifact directory. Historical
artifact-level reconstruction therefore remains `INCONCLUSIVE` and must not be
fabricated or used to rerun the bounded publication campaign.

### Current Admin QA queue

Supabase evidence was collected from project
`cjtndektjjpvvjofdvzr` between `2026-08-08T12:55:04Z` and
`2026-08-08T12:55:08Z`. Credentials were loaded by an explicit absolute
`dotenv_path` with `override=False`. Only read-only `select` and predicate RPC
calls ran.

Each scan used page size 500, deterministic ID ordering, `count='exact'`, and
unique-ID reconciliation. Both full scans returned the same normalized digest:

* 179 pending reports, 179 unique report IDs, and 154 unique event IDs
* 161 `single_auto`, 0 `compound_auto`, 18 `manual`, and 0 `empty`
* 0 active `annotation_status='error'` events
* 0 exact-pure publication errors
* 0 pending `annotation_error_stuck` reports

The two scans were byte-identical. This is read-only evidence, not a frozen
execution ledger and not permission to mutate any row.

### Live observation on 2026-08-09

A later read-only scan on 2026-08-09 counted 181 pending reports, of which 82
carried `auto_qa_missing_organizer`. That is a timestamped trend observation. It
is not an acceptance constant, and it does not replace the 2026-08-08 baseline of
179 pending reports across 154 events.

The named reports below were already inside that 179-row baseline. They are
enumerated for verification, never added to it. The queue was never 186 rows.

1. Report `280931a8-26f9-41e3-bc18-191f56a2b299` on event
   `d98cdb58-b417-4823-bcc0-119862b165be` (馬上有福-BOOK FAIR-). Its non-null
   January date is valid. Do not infer an umbrella end from nested ranges.
2. Report `ad1c1da7-92c9-4d5b-b378-e8a0bd06cbde` on event
   `135e45b2-0af4-4636-985a-fbfc92e41cc3` (春小姐 Haruトーク＆サイン会). Its
   2026-01-24 date is valid.
3. Report `c2511a20-0edd-493e-8ff6-9a24040bb55f` on event
   `e2375baf-b28d-449b-9dd9-7f0cc94aeb44` (誠品生活日本橋 春節シーズン
   「馬上有福」). Its January start is valid; its historical end is not repaired.
4. Report `12e942f9-d0eb-4314-90a3-79261bbd0454` on event
   `c1eb5e53-6779-4379-ba2a-95e8ae8e8255` (eslite Collection -夏日の奇幻旅程-).
   Generic `クリエイター` text and an unrelated Katakana subtitle are not local
   person evidence. Package A0 repairs only this event's `end_date`.
5. Report `38e5a3f1-fe1c-4a40-b2b5-32923ce0e9fb` on event
   `2b129a98-9179-4700-ad9b-0077dff9f7c8` (春節年街2026 -ワークショップ-).
   Labeled people are real evidence, so this row legitimately keeps firing.
6. Report `52076292-ef32-4b6c-abdd-07aae26aad5d` on event
   `afe674e3-332d-475e-86e1-534d97ed687c` (TOKYO CITY BOOK JAM). Organizer
   evidence remains insufficient and the event has ended.
7. Report `de88e547-f9f8-43a9-bc5f-c13d93a6f13e` on event
   `c1eb5e53-6779-4379-ba2a-95e8ae8e8255` (Summer Collection organizer). Page
   ownership and `og:site_name` do not prove organizer.
8. Report `14002d16-bed4-4fa3-af8e-e5bac7b91bc1` on event
   `1d776b95-b9fe-4822-aac2-7e067266f88e` (美山かやぶきの里冬灯廊サポーター).
   Its future January range is valid.

### Maintenance and writer state

The maintenance row exists exactly once with `active=false`, and
`admin_reports_maintenance_active()` returned `false`. All eight cleanup-related
workflow files are active in GitHub Actions: Daily Scraper, Run Merger, Error
Recovery, QA Auto Fix, QA Heartbeat, Refetch Thin Events, Annotate Now, and
Enrich and Annotate OCR Event.

The allowlisted repository variables `ERROR_RECOVERY_LIVE`,
`QA_HEARTBEAT_LIVE`, and `REFETCH_THIN_LIVE` each classify as `true`. No other
variable value was queried or reported.

The four-quadrant authorization matrix is not revalidated. Its authenticated,
anonymous, and service-role cases require controlled write attempts. That work
is `APPROVAL REQUIRED` before any future maintenance window.

## Predecessor Reconciliation

G-P, G-P.1, and Lane R are delivered. T-P is explicitly retired in the
predecessor task ledger. Proposal text that calls G-P the next delivery, says
T-P follows, or gates T-A on deployed T-P is stale.

Lane R superseded T-P for the bounded publication reset. It did not create a
generic cleanup framework. T-A therefore does not inherit a deployed-T-P
prerequisite. T-A0 must use the existing policy-neutral classifiers in
`auto_qa.py` without extracting shared helpers. A shared module is allowed only
when a later T-A mutation slice creates proven duplication with Lane R.

The predecessor `branch: origin/main` metadata remains correct as an audit
landing target. Suggested future predecessor corrections are limited to a
separately approved docs-only reconciliation or final archive:

* Replace stale G-P and T-P future tense with delivered and retired references
* Record Lane O runtime evidence and the 14-row Error Recovery settlement
* Replace the ephemeral `/memories/session/plan.md` authority pointer with this
  committed successor spec after its docs-only gate
* Preserve the missing historical artifact caveat instead of reconstructing it
* Keep predecessor `proposal.md`, `tasks.md`, and `notes.md` unchanged until that
  approval

## Delivery Packages

### Package A0: time-critical exact repair

A0.1 restores offline `lock_clean` contract coverage in
`scraper/tests/test_qa_auto_fix_unlock_only.py`. That file already covers
`unlock_only` and `lock_empty` but has no `lock_clean` case, and `lock_clean` is
the mode a future approved production repair would use. The tests extend the
existing in-memory fake, reach no network and no Supabase, and prove scalar CAS,
list and scalar `field_corrections` encoding, pre-mutation rejection, audit
finalization, and the non-transactional failure contract.

A0.2 corrects the `end_date` of event `c1eb5e53-6779-4379-ba2a-95e8ae8e8255` from
its exact stored before-image to `2026-08-31T00:00:00+00:00`, using first-party
evidence of 2026-07-18 through 2026-08-31. It is the only production mutation
anywhere in this successor, it needs its own approval naming the verbatim
before-image string, and it runs as exactly one
`qa_auto_fix.unlock_and_write(..., mode="lock_clean")` call. A `False` return
never means nothing was written: stop, re-read event, `field_corrections`, and
audit state, and require a revised approval before any retry.

### Package A: predicate and parser root cause

Package A initiates no manual production write. Scheduled system writes and
`auto_qa.py --reconcile` continue as existing runtime behaviour, and reconcile
remains the sole automatic resolver of terminal status for the affected types.

Phase 1 repairs `scraper/auto_qa.py`. Missing-date reduces to `start_date IS
NULL` as the only pure signal, dropping the broad January branch and the now
unused `PUBLISH_DATE_SOURCES` set while preserving `THIN_CONTENT_SOURCES`.
Missing-performers requires local evidence: an honorific or middle-dot personal
name in the same sentence, line, or labeled clause as the role signal, with
explicit labeled role lists still sufficient on their own. Both predicates keep
every field they read inside the detector projection and the `reconcile()`
projection, and neither mutates events or reports.

Phase 2 repairs `_extract_event_datetime_range()` in
`scraper/sources/eslite_spectrum.py` so a labeled top-level event range outranks
publication ISO text and nested item ranges, and so weekday tokens and both `～`
and `ー` separators parse. This is prospective correctness only. `upsert_events()`
skips existing Eslite rows unless forced, and reviewed rows are skipped even under
force, so deploying the parser does not repair already-stored rows.

### Explicitly not repaired

The expired Spring campaign end date, the Spring Festival performer arrays, and
the TOKYO CITY BOOK JAM organizer stay unrepaired. Those events have ended, so
the user-facing value no longer justifies exact-write governance. No January
source allowlist is added: Tokyo Art Beat already repairs Contentful placeholders
from URL slugs, so such a branch would be dead code.

## Scope

### Included

* Immutable transfer of all 39 predecessor incomplete items
* Read-only GitHub and Supabase rebaseline with exact counts and timestamps
* Package A0.1 offline `lock_clean` contract tests
* One separately approved Package A0.2 `end_date` correction
* Package A missing-date and missing-performer predicate repair
* Package A prospective Eslite date-range parser repair
* A minimal T-A0 design for discovery, classification, freeze, and review export
* Explicit prerequisites, approval gates, verification, and stop conditions
* Later separation of mutation tooling, source repair, production apply, and
  archive work

### Non-Goals

* No T-A implementation in this successor
* No push or deployment without a normal validate, merge, and deploy approval
* No workflow dispatch, workflow-variable change, or maintenance lock
* No migration, GPT run, reset, report settlement, or schema change
* No production database write outside the single approved A0.2 correction
* No repair of the expired Spring campaign, Spring Festival performers, or TOKYO
  CITY BOOK JAM organizer
* No January source allowlist, source-wide organizer default, comma-joined
  performer text, null field-correction value, or `lock_empty` sentinel
* No claim that the Eslite parser release repairs already-stored rows
* No reconstruction of the missing 204-row JSONL or the historical publication
  reset snapshot
* No predecessor edit, move, deletion, or archive
* No generic cleanup helper extraction before a second concrete consumer exists

## Design

### Phase 0: Draft review and docs-only commit

Review these two successor files against the read-only evidence. A separate
approval may then authorize a docs-only commit containing exactly
`docs/specs/active/admin-qa-cleanup/proposal.md` and
`docs/specs/active/admin-qa-cleanup/tasks.md`. The committed successor SHA and
file digests become the prerequisite for any implementation request.

### Package A0.1: offline `lock_clean` contract tests

Allowed path: `scraper/tests/test_qa_auto_fix_unlock_only.py`. The tests extend
the existing in-memory fake rather than adding a framework, and they prove:

* scalar `expected_event_value` CAS applies and returns exactly one event row
* a list value encodes through `_fc_value()` as JSON text, never `repr()` and
  never a comma join
* a scalar value encodes as exact `str(value)` text
* `expected_fc=None` rejects an unexpected row before the event is mutated
* `expected_event_value` drift rejects before the event is mutated
* success finalizes the audit row to `applied` with `event_after_value_json` set
* a post-write verification failure returns `False`, leaves the already-applied
  event and correction writes observable, and finalizes the audit row to
  `verify_failed`

The last case is the contract that matters most operationally: `False` does not
mean nothing was written.

### Package A0.2: one approved `end_date` correction

A separate approval must name event `c1eb5e53-6779-4379-ba2a-95e8ae8e8255`, field
`end_date`, the verbatim DB-returned before-image string, the new value
`2026-08-31T00:00:00+00:00`, `expected_fc=None` after a fresh full-row absence
check, an evidence digest inside `unlock_reason`, and `report_id=None` because
neither the performer nor the organizer report concerns the date field. Existing
location corrections on that event are preserve-only.

### Package A: predicate and parser repair

Allowed paths are `scraper/auto_qa.py`, `scraper/sources/eslite_spectrum.py`, and
their tests. Two contracts are tested separately because they differ:
`_check_missing_date()` is pure and applies no time window, while
`_detect_missing_date()` applies a rolling 30-day `created_at` window before it
can create a report. The known missing-performer asymmetry is preserved rather
than fixed here: `_detect_missing_performers()` selects only `performers IS
NULL`, while `_check_missing_performers()` treats both `NULL` and `[]` as
missing.

Negative fixtures assert that `auto_qa_missing_date`, `auto_qa_missing_organizer`,
and `auto_qa_missing_performers` appear in neither `qa_auto_fix.SAFE_REPORT_TYPES`
nor `qa_auto_fix.HANDLER_MAP`, and that `qa_heartbeat._fetch_pending_reports()`
enumerates only `SAFE_REPORT_TYPES`. Together they prove scheduled reconcile stays
the sole automatic terminal-status resolver for these types.

### Phase T-A0: Read-only discovery tooling

T-A0 is the smallest proposed tools-only slice. Its exact path allowlist is:

* `scraper/_oneoff_cleanup_admin_reports.py`
* `scraper/tests/test_cleanup_admin_reports.py`

No other path is allowed. In particular, T-A0 must not modify `auto_qa.py`, Lane
R tooling, workflows, migrations, web code, translations, or predecessor docs.

The proposed CLI has only `discover`, `freeze`, and `export-review` commands. It
must not expose `apply`, `rollback`, `settle`, `reset`, or lock operations. Its
core functions are:

* `fetch_pending_reports()` for deterministic, fully paginated, exact-count
  reads
* `classify_pending_reports()` using `auto_qa.classify_report_types()` and full
  report UUIDs
* `build_discovery_ledger()` for canonical report and referenced-event
  before-images
* `freeze_discovery_ledger()` requiring two byte-identical complete scans and an
  exclusive, non-overwriting artifact publish
* `export_manual_review()` for manual, unknown, empty, mixed, and payload-token
  rows

Artifacts belong under ignored `tmp/admin-qa-cleanup/<timestamp>/`, use mode
`0400`, and record query filters, exact counts, pagination, repository HEAD,
schema version, and a digest. A discovery classification is not an apply
allowlist. Known Auto-QA membership alone does not prove predicate resolution.

Tests use an injected projection-aware fake PostgREST client. Every mutator
method fails the test if called. A blocked-network fixture must prove core logic
does not create a real client or contact GitHub, Supabase, OpenAI, LINE, or any
source page. Fixtures cover more than one page, duplicate and missing IDs,
count drift, scan digest drift, full-UUID validation, every report-type class,
existing artifact refusal, and deterministic canonical output.

### Phase T-A1: Mutation tooling

Apply and rollback are a later tools-only slice. They require the committed
T-A0 implementation, a reviewed frozen ledger, exact affected functions and
tests, failure injection, complete per-field before-images, status-last writes,
and journaled observed after-images. No T-A1 approval includes a production
write.

### Phase D: Artifact-bound production operations

Each production operation requires a new immutable manifest and a literal
command. Approval must name its digest, full report UUIDs, exact action counts,
deployed tool SHA, snapshot destination, writer-state capture, maintenance
procedure, rollback boundary, and state-restoration order. Automatic batches
must exclude compound, human, mixed, unknown, empty, and payload-token rows.

### Phase S: Conditional source repair

Round S starts only when the frozen ledger proves a remaining source-owned
defect. Each source repair receives its own implementation, tests, deployment,
observation, manifest, and apply approval. Source-wide dismissal is forbidden.

## Approval Gates

* A docs-only commit requires exact two-file scope
* Package A0.1 is offline test work and authorizes no production write
* Package A0.2 requires its own approval naming the verbatim before-image, the
  new value, `expected_fc=None`, the audit reason digest, and `report_id=None`
* Package A requires an Engineer Changes Log and an independent Tester PASS
* Push requires a normal validate, merge, and deploy approval after Tester PASS
* T-A0 requires the committed successor SHA, exact path and function allowlist,
  fake-client contract, blocked-network tests, and an independent Tester PASS
* T-A1 requires a later tools-only approval and authorizes no production write
* Four-quadrant auth checks require a controlled maintenance-window approval
* Every other production mutation requires an existing artifact-bound approval
* Final predecessor reconciliation and archive require separate docs-only
  approval

## Stop Conditions

Stop on repository-base drift, worktree or branch mismatch, any dirty path
outside the approved slice, query exact-count mismatch, incomplete pagination,
duplicate or non-full UUIDs, repeated-scan digest drift, unknown report types
without manual routing, predicate projection gaps, writer-state drift, lock
state drift, an existing artifact destination, any attempted network call in
core tests, any database mutator call during T-A0, or a Tester FAIL.

Production work also stops if a report or event differs from its before-image,
a proposed automatic row contains a compound or payload token, maintenance auth
evidence is incomplete, a service-role writer is not drained, or the approved
artifact digest and literal command do not match.

Package A0 and Package A stop if predicate tests conflate the pure `_check_*()`
contract with the detector's 30-day window, if performer tests erase the known
`NULL` versus `[]` asymmetry, if the `lock_clean` tests fail to prove scalar and
list encoding, pre-mutation rejection, audit finalization, and observable partial
state, if the Eslite dry-run proposes a write or cannot match stable source IDs,
if any Package A step initiates a manual production write, or if A0.2 returns
`False` or ambiguous output and anyone attempts a retry before independently
reading actual event, correction, and audit state.

## Verification

The successor drafts must pass frontmatter assertions, Markdown diagnostics,
UTF-8 and whitespace validation, `git diff --check`, exact two-file docs scope,
predecessor hash checks, baseline checks, and worktree state checks.

Packages A0.1 and A must pass:

```bash
PYTHON="/Users/flyingship/Development/Tokyo Taiwan Radar/.venv/bin/python"
"$PYTHON" -m pytest scraper/tests/test_qa_auto_fix_unlock_only.py -q
"$PYTHON" -m pytest \
  scraper/tests/test_auto_qa_publication.py \
  scraper/tests/test_auto_qa_predicates.py \
  scraper/tests/test_event_report_consumer_eligibility.py -q
"$PYTHON" -m pytest scraper/tests/test_publication_sources.py -q
"$PYTHON" -m compileall -q scraper/auto_qa.py scraper/sources/eslite_spectrum.py
"$PYTHON" -m pytest scraper/tests -q
(cd scraper && "$PYTHON" main.py --dry-run --source eslite_spectrum)
git diff --check
```

The dry-run must write nothing. If the source network is unavailable, record the
dry-run as `INCONCLUSIVE`; fixture coverage must still pass.

The proposed T-A0 slice must later pass:

```bash
PYTHON="/Users/flyingship/Development/Tokyo Taiwan Radar/.venv/bin/python"
"$PYTHON" -m pytest scraper/tests/test_cleanup_admin_reports.py -q
"$PYTHON" -m pytest scraper/tests
"$PYTHON" -m compileall -q scraper/_oneoff_cleanup_admin_reports.py
git diff --check
```

## References

* [Predecessor proposal](../admin-reports-204-cleanup/proposal.md)
* [Predecessor tasks](../admin-reports-204-cleanup/tasks.md)
* [Predecessor critique](../admin-reports-204-cleanup/notes.md)
* [Workstream tracking](../workstream-tracking/tasks.md)
* [Spec lifecycle](../../README.md)
