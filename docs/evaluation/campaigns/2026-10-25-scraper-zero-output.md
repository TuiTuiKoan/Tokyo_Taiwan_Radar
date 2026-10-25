---
title: Scraper Zero Output Close-out
description: Records that scrapers returning zero events now fail loudly, that the three GitHub-blocked sources run weekly from a home IP, and what stays open
ms.date: 2026-10-25
ms.topic: reference
keywords:
  - campaign close-out
  - scraper
  - zero output
  - home-IP run
  - worktree disposition
estimated_reading_time: 5
---

## Outcome

Six sources (`mot`, `taipei_fukuoka`, `jposa_ja`, `tokyo_art_beat`, `tokyo_now`, `bookandbeer`) had been recording "success, 0 events" in `scraper_runs`. The causes were measured from a GitHub Actions runner and differ per source:

* `mot` answers 403 to every path from GitHub Actions IPs. `taipei_fukuoka` and `jposa_ja` are redirected by CloudFront to an error page that `requests` follows into a 200 HTML. The reason for the redirect (WAF or IP reputation) is inferred, not confirmed by the site.
* `tokyo_art_beat` was not a token problem. The old Contentful space is frozen at 18 events; live data is served by the CDA proxy, which the scraper now reads.
* `tokyo_now` is now an entertainment news site without an events calendar, so it was retired.
* `bookandbeer` has working selectors; zero Taiwan-related events is the correct result.

In production now: every list or API failure raises, so `main.py` records `success=false`. The three blocked sources are skipped in the CI daily run and run every Monday 15:00 JST from a home IP through launchd. A single-source run enriches only its own new events (about 2 minutes instead of 25 or more). Manual Daily Scraper run 40067900799 and the scheduled run of 2026-10-25 both finished with `success`.

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `1ff94651` | `tokyo_art_beat` reads the live CDA proxy and fails loudly (#375) | yes |
| `343a613b` | `tokyo_now` raises on API failure; the calendar is documented as gone (#376) | yes |
| `2a529c33` | `bookandbeer` raises when listing page 1 has no cards (#377) | yes |
| `7a24ac6a` | `mot`, `taipei_fukuoka`, `jposa_ja` fail when the list endpoint is blocked (#378) | yes |
| `fc02c1d7` | Retire `tokyo_now` (user decision) | yes |
| `27554bf8` | Single-source runs enrich only their own new events (#395) | yes |
| `27b9539e` | Run the GitHub-blocked sources weekly from a home IP (#378) | yes |
| `069b7751` | Add the `scraper-zero-output` spec | yes |
| `7767644e` | Regression test that resolves enrichment script annotations (#424) | yes |
| `17bb2355` | `source_expectations.json`: blocked sources and `bookandbeer` become sporadic, `tokyo_art_beat` removed | yes |
| `18cbb644` | Archive the spec | yes |

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| Root causes measured from GitHub Actions | PASS | Probe runs on ubuntu-24.04 reproduced the 403 and the CloudFront redirect; the CDA proxy returned 1740 upcoming events with the existing token |
| Scraper test suite | PASS | `pytest` in `scraper/` after the last rebase: 1602 passed, 1 skipped |
| Adapter sync | PASS | `scripts/sync_ai_adapters.py --check` exits 0 |
| `scraper_runs` for the six sources after the fix | PASS | `tokyo_art_beat` 10 and 20 events, `bookandbeer` 0 events, both `success`; no `tokyo_now` rows; no CI rows for the three blocked sources |
| Home-IP weekly run, first execution (2026-10-23) | PASS | Exit 0 in 2m18s; `scraper_runs` ids 17515 to 17517 all `success`; log shows enrichment restricted to 3 ids |
| Manual Daily Scraper, run 40067900799 at `17bb2355` | PASS | Conclusion `success`; "Enrich missing location addresses via GPT" and "Fail on LLM step errors" both passed |
| Scheduled Daily Scraper of 2026-10-25, run 40156531219 | PASS | Conclusion `success` |
| Second and later home-IP runs | NOT TESTED | Only the first run was observed. Residual risk: the launchd job reads its scripts from the main checkout, so it runs whatever that checkout holds |
| Source output volume of the three blocked sources over weeks | NOT TESTED | `source_expectations.json` now treats them as sporadic; a real quiet period longer than `max_quiet_days` has not been observed |

## Correction and supersession

None.

## Known risks

* Issues #394 (`taipei_fukuoka` keyword `お知らせ` admits non-event notices) and #404 (`_ensure_scrapers_registered` writes `url=''` and hits `research_sources_url_key`) stay open. The user accepted both as follow-up work on 2026-10-25.
* The weekly home-IP run depends on the user's Mac being awake near Monday 15:00 JST (launchd runs a missed job on wake) and on the main checkout being current. At the audit the local `main` of the main checkout was 13 commits behind `origin/main`.
* The cause of the roc-taiwan.org block is an inference. If the site changes its policy, the weekly run needs no change, but the CI skip list could be reviewed.
* `jposa_ja` recap posts about officials attending events become public events. This predates the campaign and was left unchanged.
* The close-out audit script searches open issues by slug text, not by the `spec:<slug>` label, so it reported 0 where #394 and #404 are open. Found by a manual `gh issue list --label` check.

## Deferred work

* #394 and #404, both labelled `spec:scraper-zero-output`, track the two open follow-ups.
* Tightening the `jposa_ja` filter so attendance recaps are not published as events: not done, not yet tracked by an issue.
* Teaching `scripts/campaign-closeout-audit.sh` to count open issues by `spec:<slug>` label: not done, not yet tracked by an issue.

## Spec disposition

`archive` for `docs/specs/active/scraper-zero-output/`, because every milestone is checked and the work is on `origin/main`. It now lives in `docs/specs/archive/2026-10-scraper-zero-output/` (commit `18cbb644`).

## Worktree disposition

`pending`. The disposition is decided after this record lands on `origin/main`; the final section is backfilled from the recovery capsule. The user confirmed on 2026-10-25 that no other session uses this worktree. Two terminal shells still had their working directory in it at the Phase A audit and must be closed before removal.

## Ignored artifacts and handling

* `.pytest_cache/`, `scraper/.pytest_cache/` and `scraper/**/__pycache__/`: `disposable`. Regenerated by pytest and Python. No digest, because they are regenerable.
* `scraper/auto_scraper/runs/42/`: `disposable`. Output of the test suite (`budget-exceeded` for the placeholder source `example.com`, with an empty `sample.html`); any pytest run regenerates it. No digest.
* `scraper/.env`: absent in this worktree by design, so nothing to preserve.

## Evidence anchors

None. The anchor generator reads Copilot CLI transcripts only, and this campaign ran in Claude Code sessions, so no telemetry anchor or ledger could be produced.
