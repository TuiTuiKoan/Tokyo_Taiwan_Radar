# LivePocket Scraper History

## 2026-04-29

### Initial implementation

**Findings:**
- Site renders static HTML; no Playwright or JS needed
- `robots.txt` has no Disallow rules — open crawling confirmed
- Search URL pattern: `/event/search?word={keyword}&page=N`; returns 404 on out-of-range pages
- Three keywords used: `台湾`, `Taiwan`, `臺灣`

**Critical CSS selector mistake (caught in dry-run):**
- Assumed `dl` class was `event-detail-info` (from initial visual inspection)
- Actual class is `event-detail-info__list`
- `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` divs, not direct children of `dl`
- Fix: use `soup.select_one("dl.event-detail-info__list")` and iterate `div.event-detail-info__block`

**Class name convention:**
- Class name `LivePocketScraper` produces `_scraper_key` = `live_pocket` (CamelCase split)
- But `source_name = "livepocket"` would conflict
- Solution: rename class to `LivepocketScraper` → `_scraper_key` = `livepocket`

**Result:** 14 Taiwan events found on first dry-run after fix; `start_date` populated for all.
