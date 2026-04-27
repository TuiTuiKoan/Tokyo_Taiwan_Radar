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
