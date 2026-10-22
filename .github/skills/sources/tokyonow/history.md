# Tokyo Now Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-10-23 — Events API 404 since ~2026-09; site is now a news media (#376)

**Error:** `scraper_runs` shows no output since 2026-09-14; dry-run: `404 Client Error` on `/wp-json/tribe/events/v1/events`. The failure was logged but `_fetch_page` returned `None`, `scrape()` returned `[]`, so every weekly run was recorded as `success=True, 0 events`.

**Root cause:** tokyonow.tokyo removed The Events Calendar and became an entertainment news site. No event post type, sitemap or HTML list exists any more (checked `wp-json`, `wp/v2/types`, `sitemap.xml`, `/events/` → `/information/`, `event_area` taxonomy empty).

**Fix:** `_fetch_page` no longer swallows errors: HTTP errors and payloads without `events` raise, so the run is recorded as failed. No rewrite is possible; retiring the source is the follow-up.

**Lesson:** a scraper that catches its own list/API failure and returns `[]` is indistinguishable from "no events" in `scraper_runs`. List/API errors must raise; only per-detail-page failures may be skipped.

---

## 2026-04-26 — Initial implementation: API keyword search returns 0

**Error:** `GET /wp-json/tribe/events/v1/events?search=台湾` returns 0 results despite Taiwan events existing on the site.

**Root cause:** The Tribe Events v1 API `search` parameter only matches against the English title/slug; it does not search Japanese text fields.

**Fix:** Full-page scan strategy — paginate through ALL upcoming events (`start_date=<today>`, `per_page=50`) and apply local keyword filter (`_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]`) on `_strip_html(title + description)`.

**Lesson:** Never assume a CMS/plugin search API supports Japanese full-text search. Test with a known Japanese keyword before relying on server-side filtering.

---
