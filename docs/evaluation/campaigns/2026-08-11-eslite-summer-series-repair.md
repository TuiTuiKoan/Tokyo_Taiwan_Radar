---
title: Eslite Summer Series Repair Closeout
description: Production outcome, evidence, and remaining work for the 2026 Eslite summer event-series repair
ms.date: 2026-08-11
ms.topic: reference
keywords:
  - eslite
  - campaign repair
  - venue ground truth
  - event hierarchy
estimated_reading_time: 8
---

## Outcome

The Eslite summer event-series repair is complete in production. The canonical
campaign now has one parent and seven direct children, the merchandise-only
price no longer represents campaign admission, event-specific schedules remain
authoritative, and verified general venue hours are available as reusable venue
ground truth.

This closeout applies only to the Eslite summer series. The broader
`admin-qa-cleanup` specification remains active for separately approved queue
tooling, production-window governance, scheduled observations, and archive work.

| Field                     | Result                                                        |
|---------------------------|---------------------------------------------------------------|
| Campaign status           | Closed                                                        |
| Canonical parent          | `074ec240-3463-4c42-8cab-2ea348b93f5c`                        |
| Parent and direct children| 8 total                                                       |
| Duplicate campaign row    | Redirected to the canonical parent                            |
| Venue ground truth        | 1 authoritative `誠品生活日本橋` row                          |
| General-hours events      | 4                                                             |
| Event-specific schedules  | 4 preserved                                                   |
| Field corrections         | 12 clean locks across Japanese, Traditional Chinese, and English |
| Correction audits         | 12 `applied` rows                                              |

## Incident

The campaign exposed four connected defects:

* An unlabeled `6,980円` tea-gift price was interpreted as the admission price
  for the complete campaign.
* Independently dated and conditioned items on the umbrella page were not
  represented as direct child events.
* A nested item schedule leaked into the parent while general store hours were
  absent from authoritative venue data.
* Exact-only venue lookup could not enrich labels such as `expo`, `書籍レジ`,
  and `各ショップ` without replacing their useful subspace names.

The surrounding Admin QA investigation also found a January date heuristic that
treated valid event dates as placeholders, a missing-performer predicate that
combined unrelated role and name tokens, and Eslite date parsing that allowed
publication or nested dates to outrank a labeled top-level range.

## Authoritative Evidence

The official campaign and venue pages were the first-party sources:

* [Summer campaign overview](https://www.eslitespectrum.jp/news/85683cc0-cbde-4cfe-bc7e-d46468d7a998)
* [Eslite Spectrum Nihonbashi store page](https://www.eslitespectrum.jp/about/store/9cd1340f-26b6-4f55-9c33-d0487d7ac01d)

The store page states the general hours as
`平日 11:00～20:00、土日祝 10:00～20:00`. Restaurant and tenant exceptions were
not promoted to the venue-wide value.

## Production After-Image

The production read-back completed on 2026-08-11 with this reconciliation:

```text
venue=1
parent+children=8
general-hours events=4
event-specific schedules=4
field_corrections=12
applied audits=12
```

The authoritative venue row is
`fd330e2a-e8e8-40fb-9fcb-d1af44d7be3a`. It stores the official store page and
the verified general hours. Summer hierarchy manifest `4f25dfc756d3` identifies
the parent, child, pricing, and redirect repair. Its correction audits ran from
`2026-08-09T21:52:50.401181Z` to `2026-08-09T21:53:29.089863Z`, six child rows
were inserted at `2026-08-09T21:53:29.721030Z`, and the final duplicate redirect
ran from `2026-08-09T21:53:31.250239Z` to
`2026-08-09T21:53:31.541644Z`.

Venue-hours manifest `5742d0438ed9` identifies the venue mutation and its
correction-audit set. Its verified interval is
`2026-08-09T22:09:12.030295Z` through
`2026-08-09T22:09:31.152860Z`.

### Event Inventory

| Event | Hours policy |
|-------|--------------|
| [夏日の奇幻旅程～夏休みのファンタジック・ジャーニー～](https://tokyotaiwanradar.com/ja/events/074ec240-3463-4c42-8cab-2ea348b93f5c) | General venue hours |
| [eslite Collection -夏日の奇幻旅程-](https://tokyotaiwanradar.com/ja/events/dda72a62-ad44-4aa4-aa23-33c942b06a92) | General venue hours |
| [普段使いの魔法道具マーケット『まいにち魔法』](https://tokyotaiwanradar.com/ja/events/5e8767c4-d89b-44c2-a995-a617db66eb8f) | General venue hours |
| [eslite welcome weekend! 誠品会員限定抽選会](https://tokyotaiwanradar.com/ja/events/5a5e27fc-68bf-4152-9830-9b4ed9228ad2) | General venue hours |
| [星空台湾夜市 -夏日の奇幻旅程-](https://tokyotaiwanradar.com/ja/events/f573eb8b-665e-4158-a4ef-b94c92d81fcc) | Event-specific schedule preserved |
| [星空抽選会](https://tokyotaiwanradar.com/ja/events/86545b32-506d-4718-97e7-93c4ea2968bb) | Event-specific schedule preserved |
| [夏だ‼ 黒橋牌台湾ソーセージだ‼](https://tokyotaiwanradar.com/ja/events/55e2a629-c4a5-4ec6-94af-c123e90ef47c) | Event-specific schedule preserved |
| [アート＆シネマ抽選会](https://tokyotaiwanradar.com/ja/events/c2d7a7b2-a236-43b8-8929-a9127fba1eaf) | Event-specific schedule preserved |

## Delivered Changes

| Commit | Delivery |
|--------|----------|
| `738fd9e8004fa4e0230b3cd22479c43ef62356bd` | Restructured the Admin QA successor into Package A0 and Package A |
| `784653d87461d659090eea17e63e539b51d00900` | Added `lock_clean` compare-and-set, encoding, and partial-failure contract coverage |
| `0f347f81fb238e4313691202d90ff48a7ac4687d` | Removed the January heuristic and required local performer evidence |
| `93513aa1e7f5cf87e7c7b6eb81483a4661b89798` | Made labeled top-level Eslite ranges outrank publication and nested dates |
| `5c5a6deede589a32f372a6ea3244b5a9c13c391e` | Repaired pricing, event hierarchy, venue hours, registry inheritance, and operational guidance |
| `0a1a8c8e72eaf276cdcadffc534ab7b95cc52554` | Published the original campaign closeout evidence |

All six commits are ancestors of `origin/main`. The forward release candidate
then adds exactly these three subjects:

* `fix(scraper): harden Eslite venue release`
* `chore(skills): align Eslite release guidance`
* `docs: reconcile Eslite and admin QA evidence` (this update; hash intentionally
  omitted)

The exact three post-commit SHAs belong in the Engineer Changes Log, Tester
report, and V-M-D approval so a clean rebase cannot make this report stale.

Natural Daily Scraper run `31345880622` completed successfully at head
`39dbba0e7b923f8b003da0566bbd3da1a8d1639b` and covered the first four delivery
commits only. Run `31447829421` completed successfully from a scheduled event at
head `dc1d23873c790bb0f16fe41ac4ad96cfd7bc2bff`. That head descends from all six
published commits, but not from the three forward candidate commits. A later
successful natural run whose head descends from all three forward commits is
still required.

## Prevention Rules

The delivered behavior establishes these contracts:

1. An amount is an event fee only when the source labels it as a fee, admission,
   or participation charge. Merchandise prices and purchase thresholds do not
   determine parent-event admission.
2. Independently dated, located, or conditioned campaign items become direct
   child events.
3. Hours follow `event-specific schedule > authoritative venue hours > UI
   source-link fallback`.
4. General venue hours come only from a first-party store, access,
   visitor-information, or opening-hours page.
5. Canonical venue subspaces inherit verified parent metadata while preserving
   their specific location labels. Broad aliases cannot capture prefix matches.

The Scraper Expert agent, shared skill copies, Eslite source skill, and their
history files record the same contracts.

## Validation

The forward candidate's pre-evidence Phase 3 validation produced these results:

* The five-file focused set passed 75 tests in 5.79 seconds, with 6.70 seconds
  wall time. It covers venue-overlay `BYPASSED`, `MATCHED`, and `MISS` outcomes,
  two-payload subspace-label preservation, field-correction empty sentinels,
  protected-attempt counts, homepage fallback, and both retired one-off apply
  paths.
* Six target Python files compiled successfully in 0.12 seconds wall time.
* The complete scraper suite passed 834 tests, skipped 1, and emitted 25 known
  deprecation warnings in 15.61 seconds, with 16.42 seconds wall time.
* The read-only post-build audit passed in 2.96 seconds. All scrapers were
  registered, and all implemented research sources had a source key.
* The write-free Eslite source smoke completed with exit code 0, found 738 news
  items, emitted 37 events, printed the explicit `DRY RUN` no-write marker, and
  took 648.16 seconds wall time.
* Editor diagnostics reported no errors across the 15 candidate paths.
* YAML frontmatter parsing, stale-claim searches, replacement-character checks,
  conflict-marker checks, EOF-newline checks, and `git diff --check` passed.

The independent production read-back also passed for the venue, eight events,
12 corrections, and 12 audit rows. Final-tree Phase 5 validation and final
independent Tester approval remain release gates after this evidence commit.

## Data Lifecycle

Venue ground truth is a curated snapshot, not a live reference to the official
page. No scheduled workflow currently fetches the store page and updates
`venues.business_hours` when its text changes.

The 12 event field corrections have no expiry. Normal scraper, annotator, and
venue-propagation paths cannot overwrite them. They remain reversible through
an explicit correction update or `unlock_only` operation with a new review and
audit trail.

New events with empty hours may inherit the current venue value. Existing events
with a non-empty schedule or a field correction do not automatically follow a
later venue update. This preserves historical event display but requires an
explicit propagation decision for future active events when official hours
change.

## Remaining Work

The production data repair is complete, and the remaining release hardening is
implemented in the forward candidate. Final-tree validation, independent Tester
approval, explicit push approval, and a later descendant natural run remain
required before the forward closeout is released.

One optional future enhancement remains outside this campaign: monitor the
first-party venue page, detect a change, open a review item, and propagate an
approved value with effective-date and field-correction awareness. Automatic
unreviewed replacement is not recommended because venue pages often mix general
hours with restaurant, cinema, and tenant exceptions.

The broader `admin-qa-cleanup` specification remains active. Its remaining work
includes read-only queue tooling and freeze artifacts, mutation tooling,
artifact-bound production windows, natural scheduled observations, final scans,
and docs-only archive approval. T-A0, P0, T-A1, Phase D, Phase S, and final
Closeout remain unapproved.

## Worktree Disposition

The original evidence commit `0a1a8c8e` is a published `origin/main` ancestor.
This update is the third commit in a forward candidate after the runtime and
customization commits named above. Keep `ttr-admin-qa-cleanup-worktree` mounted
while final Tester validation and the approved release cycle are pending. Any
later removal requires a fresh check that the worktree is clean, every candidate
commit is published, no Git operation is active, and no unique evidence remains.
Removing a worktree never archives or closes the active Admin QA specification.
