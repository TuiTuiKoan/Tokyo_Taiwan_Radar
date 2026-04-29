# maruhiro Scraper History

## 2026-04-29 — Initial implementation

**Trigger:** 丸広百貨店川越店「台湾フェア」が prtimes 経由で発見されたため、百貨店直接スクレイパーを実装。

**Key decisions:**
- Detail pages contain only a JPEG image — all useful data (title, date, store, floor) is in the list page cards. No detail page fetch needed.
- source_id uses the integer in `data-url="/events/view/{id}"` — stable across runs.
- `start_date` must be `datetime.datetime` (not `datetime.date`) — `dedup_events` in `base.py` calls `.date()` on it, which fails if a bare `date` is passed. Bug found during first dry-run.
- Pagination: last page number extracted from `a[href*="page:"]` links. Confirmed 13 pages on 2026-04-29.
- Store address resolved from static `_STORE_ADDRESS` dict keyed by the store name fragment from `開催店舗:` text.

**Bug found at implementation:** `AttributeError: 'datetime.date' object has no attribute 'date'` — `_parse_dates` initially returned `datetime.date` objects. Fixed to return `datetime.datetime`.

**Additional finding:** During SCRAPERS registration audit after implementing maruhiro, discovered that `7aecfef` (chore: tighten workflow guards) had removed 15 scrapers from main.py:
- EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper
- CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper
- ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper
- GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper

All 15 were restored in the same commit as maruhiro. Total: 56 scrapers registered.

**dry-run result:** 1 event — 台湾フェア (川越店, 2026-04-29〜2026-05-04) ✓
