# Waseda ICL Scraper — History

<!-- Append new entries at the top -->

---
## 2026-05-05 — Initial implementation

**Decisions made:**
- Used WP REST API (`/wp-json/wp/v2/posts?search=台湾`) instead of HTML scraping. ICL's subdirectory is NOT Cloudflare-blocked, unlike the main `waseda.jp` domain.
- Two-stage filter: API `search=` parameter for initial recall, then `_TAIWAN_TITLE_RE` on title for precision. Body-only mentions (e.g. Taiwan in bibliography) are excluded.
- `_REPORT_RE` skips 開催報告 posts — these are event summaries posted AFTER the event and would return stale dates.
- `LOOKBACK_DAYS = 120` chosen because legal symposium announcements are posted up to 3 months in advance.
- **Implementation note**: commit `045d1fa` created `waseda_icl.py` and added import + SCRAPERS entry, BUT silently dropped 24 other scrapers in the same edit. Restored in `6a83c64`.

---
