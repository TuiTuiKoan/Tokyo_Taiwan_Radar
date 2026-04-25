# Tokyo Now Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-04-26 — Initial implementation: API keyword search returns 0

**Error:** `GET /wp-json/tribe/events/v1/events?search=台湾` returns 0 results despite Taiwan events existing on the site.

**Root cause:** The Tribe Events v1 API `search` parameter only matches against the English title/slug; it does not search Japanese text fields.

**Fix:** Full-page scan strategy — paginate through ALL upcoming events (`start_date=<today>`, `per_page=50`) and apply local keyword filter (`_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]`) on `_strip_html(title + description)`.

**Lesson:** Never assume a CMS/plugin search API supports Japanese full-text search. Test with a known Japanese keyword before relying on server-side filtering.

---
