# eslite_spectrum — History

Newest at top.

---

## 2026-04-26 — 誠品 keyword false positive issue

**Error**: All 5 news articles were matching the Taiwan filter when `"誠品"` was included in `TAIWAN_KEYWORDS`.

**Root cause**: `"誠品"` appears in every page's navigation sidebar and footer (e.g. "誠品生活メンバーズカード", "誠品生活日本橋について"). When checking `page_text` (full page HTML), every article triggered the Taiwan filter.

**Fix**:
1. Removed `"誠品"` from `TAIWAN_KEYWORDS`.
2. Changed the keyword check to use `content_text = f"{title}\n{description}"` (main content only), not the full `page.text`.
3. Added `_SKIP_TITLE_RE` to pre-filter admin articles (membership, workshop calendars, notices) before fetching detail pages.

**Lesson**: For venue/shop scrapers, always check keywords against main content only, not the full page. Site-name branding in nav/footer will trigger false positives.
