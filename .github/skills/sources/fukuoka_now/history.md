# Fukuoka Now Scraper History

## 2026-04-29 — Initial implementation

- Implemented `FukuokaNowScraper` in `scraper/sources/fukuoka_now.py`
- Static HTML scraper using `requests` + `BeautifulSoup` — no Playwright needed
- Taiwan filter: `["台湾", "Taiwan", "Taiwanese", "臺灣"]` applied to title + tags + card description
- Dedup key: `fukuoka_now_{slug}` from URL last path segment
- Confirmed Taiwan event: 台湾祭 in 福岡 2026 (Jan 30 – Feb 23) — detail page parses correctly
- dry-run returned 0 events (correct: 台湾祭 已終了, 次回イベントは未掲載)
- All unit tests passed: filter, slug, date parsing, card→Event, detail page parsing
- `_extract_venue()`: line-based venue extraction from English description paragraphs
- Category inference: tags mapped to canonical categories + `taiwan_japan` always added
