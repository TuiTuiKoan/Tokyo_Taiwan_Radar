## 2026-11-08

### Removed the one-off start_date correction script (#595, refs #537)

- **Removed**: `scraper/_oneoff_fix_eiga_com_theater_start.py` and its three `test_oneoff_*` tests. It was never applied. Run after the real start date had passed, its dry-run proposed the scrape day (2026-11-08 for Image Forum, whose true start is 11/7), because the area page only lists today onward; `--apply` would have written that value and keep-earliest would have locked it in. Since #573 new theater rows no longer inherit 公開日, so the script has no remaining targets.
- **Existing rows fixed by hand** (Supabase SQL editor, user-run): `ea660d3d…` start → `2026-11-07T00:00:00Z`; `ab35e227…` start `2026-10-14T15:00:00Z` → `2026-10-15T00:00:00Z`.
- **Do not set `force_rescrape=true` on eiga_com theater rows**: forced rows are fully overwritten and bypass keep-earliest, so start would become the scrape day.
- **Checked 2026-11-08** (user-run, #595): in the sampled area pages every `td[data-date]` carried screenings (no empty cells), and a theater page shows the same week as its area page with no theater-level start date. Remaining accepted limits (grace-window starts, same-theater revivals, first observed after the start date) are tracked in #546.

## 2026-11-07

### Per-theater start_date (#537)

- **Symptom**: シアター・イメージフォーラム's revival of 日曜日の散歩者 started 11/7 (映画.com news 2026-10-05: Stranger 10/10–15, Image Forum from 11/7), but the event showed a mid-October start — every theater inherited the film's 劇場公開日.
- **Fix**: `_theater_start_date()` uses the first observed screening when it is more than 7 days after 公開日. `database._build_movie_extend_row` keeps MIN(start) for `eiga_com` (the area page only shows the current week, so "prefer new start" would slide forward weekly) and normalizes legacy JST-midnight values (`T15:00:00Z`, pre-#547) before comparing.
- **Existing rows**: `_oneoff_fix_eiga_com_theater_start.py` (dry-run default) proposes corrections for rows created > 7 days after their stored start; `--apply` is a production write and needs user approval.
- **Known limit**: a theater showing since release but first observed > 7 days later (e.g. scraper outage) gets its first observed date. Cross-source date reconciliation is tracked in #546.

## 2026-11-07

### Calendar dates stored as UTC midnight (#547)

- **Symptom**: `_parse_date()` / `_yyyymmdd_to_date()` used `tzinfo=_JST`, so DB held the previous day 15:00 UTC and the site (timeZone UTC) showed every date one day early.
- **Fix**: both functions now use `tzinfo=timezone.utc`; `self._today` is today's JST date at UTC midnight so lookback/lookahead comparisons stay consistent. Test: `scraper/tests/test_eiga_com_dates.py`.
- **Not changed**: how start_date is chosen and existing production rows (see #537).

## 2026-04-27

### Per-theater event redesign

- **Trigger**: User requested per-theater granularity — one event per cinema with `start_date` (pub_date) and `end_date` (last scheduled date).
- **Old model**: 1 movie → 1 event, `source_id = eiga_com_{movie_id}`, `location_name=None`, `end_date=None`.
- **New model**: 1 movie × N theaters → N events, `source_id = eiga_com_{movie_id}_{theater_id}`, `location_name = theater_name`, `location_address`, `end_date = last td[data-date]`.
- **URL flow discovered**:
  - `/movie/{id}/theater/` → area links (`/movie-area/{id}/{pref}/{area}/`)
  - `/movie-area/{id}/{pref}/{area}/` → `div.movie-schedule[data-theater]` blocks + `.more-schedule a.icon.arrow` for theater_id
  - `/movie-theater/{id}/{pref}/{area}/{theater_id}/` → `table.theater-table` → 住所
- **Bugs fixed during implementation**:
  1. `more-schedule` has 3 links (copy/print/all-schedule); first link is `/mail/` not the detail page. Fix: use `a.icon.arrow` selector.
  2. Address regex matched JS-embedded `東京都` on area page. Fix: use `theater-table th=住所 + td` on theater page.
  3. `td.get_text()` included `<a>` link text "映画館公式ページ". Fix: `a_tag.decompose()` before `get_text()`.
- **Dry-run result**: 1 event — `eiga_com_82162_3018`, `location_name=K's cinema`, `location_address=東京都新宿区新宿3-35-13 3F`, `start_date=2026-04-25`, `end_date=2026-05-01`.
- **Fallback**: if no area links found, emit one movie-level event with `location_name=None`.

## 2026-04-26

### Initial implementation

- Implemented `EigaComScraper` for 映画.com 台湾映画 search results.
- Source URL: `https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/` (up to 5 pages)
- Date filter window: today-90 days to today+180 days to exclude stale old Taiwan films (e.g. 2020 releases still in search index).
- Dry-run result: 1 event — "台湾ハリウッド" (2026-04-25), source_id `eiga_com_82162`. start_date correctly set from `p.date-published`.
- research_sources id=70 updated to `implemented`.
- Decision: `location_name=None` because this is a nationwide release film, no single Tokyo cinema specified.
- Decision: synopsis extracted from first bare `<p>` with no class and len>80 chars.
