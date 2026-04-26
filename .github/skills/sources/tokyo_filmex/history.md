## 2026-04-26

### Initial implementation

- Implemented `TokyoFilmexScraper` for 東京フィルメックス.
- Domain: `filmex.jp` (NOT `filmex.net` — returns 114 bytes redirect HTML, not actual content).
- Year detection: parse first 4-digit year from `/program/fc/` page `<title>` tag.
- Current state: festival_year=2025 < today.year=2026 → scraper returns `[]`. Expected behavior.
- Dry-run result: 0 events (as expected — 2026 program not yet published).
- research_sources id=59 updated to `implemented`.
- Decision: `festival_year < today.year → return []` immediately to avoid processing stale past data.
- Decision: Taiwan filter = first bare `<p>` in `div.textWrap.areaLink` starts with `"台湾"`.
- Decision: Venue abbrev map: `朝日` → 有楽町朝日ホール, `HTC` → ヒューマントラストシネマ有楽町.
- Decision: source_id format `tokyo_filmex_{year}_{cat}{num}` — cat=`fc`/`ss`/`mj`, num=detail file number.
- Lesson: Scraper will activate automatically when 2026 program goes live (~October 2026).
