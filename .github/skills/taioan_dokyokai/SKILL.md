---
name: taioan_dokyokai
description: Platform rules, date extraction, and report detection for the 在日台湾同郷会 scraper
applyTo: scraper/sources/taioan_dokyokai.py
---

# taioan_dokyokai Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://taioan.fc2.page` |
| CMS | WordPress on FC2 |
| Rendering | Playwright (`sync_playwright`) |
| Auth required | No |
| Rate limit | Implicit; scraper yields 0.5–1 s between requests |
| Source name | `taioan_dokyokai` |
| Source ID format | MD5 hash of article URL (first 16 chars) |

## Listing Categories

| URL Path | Category hint |
|----------|---------------|
| `/category/event/` | `[]` — annotator decides |
| `/category/%e6%b4%bb%e5%8b%95%e8%a8%98%e9%8c%b2/` (活動記録) | `["report"]` |

Pagination: WordPress `/page/N/` scheme, up to `MAX_PAGES = 5` per category.
90-day lookback cutoff applied on **publish date** (not event date).

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | MD5 hash of article URL, first 16 chars |
| `raw_title` | `<h1>` / article heading |
| `start_date` | `_extract_taioan_event_dates()` → `_extract_event_dates_from_body()` → `_extract_prose_date_range_from_body()` (imported from `taiwan_cultural_center`) |
| `end_date` | Same extraction; set to `start_date` if single-day |
| `location_name` | From body text: `会場：` / `場所：` label |
| `raw_description` | Full article body text |

## Date Extraction — 4-tier cascade (shared with TCC)

This source uses `■ 日時` labels **without a colon**, followed by the date on the next line:

```
■ 日時
  2026年05月10日（日）
  13:00～16:15
```

`_TAIOAN_DATE_LABEL` regex handles this variant (allows optional newline between label and value).

Cascade:
1. `_extract_taioan_event_dates()` — extended Tier 1 with optional-newline label matching
2. `_extract_event_dates_from_body()` — TCC Tier 1 (labeled date with colon)
3. `_extract_prose_date_range_from_body()` — TCC Tier 3 (prose date range)
4. Publish date fallback — only if all above fail (risky; may return article publish date)

## Report Detection

Articles under `/category/活動記録/` are seeded with `category=["report"]`.
The annotator will add further sub-categories based on content.

## Dependency on TCC Module

Date extraction functions are imported from `taiwan_cultural_center.py`:

```python
from .taiwan_cultural_center import (
    _extract_event_dates_from_body,
    _extract_prose_date_range_from_body,
    _parse_date,
)
```

If `taiwan_cultural_center.py` is refactored, verify these imports remain valid.

## Pending Rules

<!-- Added automatically by confirm-report -->
