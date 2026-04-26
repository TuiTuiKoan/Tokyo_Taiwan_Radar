## 2026-04-26

### Initial implementation

- Implemented `EigaComScraper` for 映画.com 台湾映画 search results.
- Source URL: `https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/` (up to 5 pages)
- Date filter window: today-90 days to today+180 days to exclude stale old Taiwan films (e.g. 2020 releases still in search index).
- Dry-run result: 1 event — "台湾ハリウッド" (2026-04-25), source_id `eiga_com_82162`. start_date correctly set from `p.date-published`.
- research_sources id=70 updated to `implemented`.
- Decision: `location_name=None` because this is a nationwide release film, no single Tokyo cinema specified.
- Decision: synopsis extracted from first bare `<p>` with no class and len>80 chars.
