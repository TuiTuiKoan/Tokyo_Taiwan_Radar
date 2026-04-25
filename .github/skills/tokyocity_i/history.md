# 東京シティアイ Scraper — Error History

<!-- Append new entries at the top -->

---

## 2026-04-26 — Initial implementation: year typo on listing-page dates

**Observation:** The event listing page showed `"2026/5/8（金）～2025/5/10（日）"` — the end year was `2025` instead of `2026` (WordPress data entry error). Using listing-page dates directly would produce an `end_date` in the past.

**Fix:** Always use the `期間` row from the **detail page table** as the authoritative date source. Listing-page dates are display-only and may contain typos.

**Lesson:** For WordPress sites with a structured detail table, always prefer table values over listing-page snippets for dates.

---
