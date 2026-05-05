# ArtistcafeScraper — History

<!-- Append new entries at the top -->

---
## 2026-05-05 — Taiwan filter missing; raw_description was nav header text

**Error:** Auto-generated scraper assumed `?keyword=台湾` would filter Taiwan events, but artistcafe.jp ignores the parameter entirely. All 12 listing cards were collected regardless of Taiwan relevance. Additionally, `body.inner_text()` on the detail page captured navigation text (`OPEN 11:00 - 19:00 アクセス …`) instead of actual event content.

**Result:** 14/17 non-Taiwan events in DB (e.g. 演技ワークショップ, 美術解剖学, 武田憲人個展).

**Fix (commit TBD):**
1. Removed `SEARCH_KEYWORD` and `?keyword=` from listing URL
2. Added `_TAIWAN_KEYWORDS` + `_is_taiwan()` function
3. Added `DETAIL_CONTENT_SELECTOR = "article"` — use `<article>` for description
4. Added `_is_taiwan(title + description)` gate in `_extract_cards()`
5. DB cleanup: 14 non-Taiwan events set to `is_active=False`

**Lesson:** Always verify `?keyword=` filter by comparing results with and without the param. If counts are equal, the site ignores it — implement `_is_taiwan()` in-scraper.
