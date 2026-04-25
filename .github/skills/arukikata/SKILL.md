---
name: arukikata
description: Platform rules, sitemap monitoring, dual-keyword title filter, and date extraction for the 地球の歩き方 scraper
applyTo: scraper/sources/arukikata.py
---

# arukikata Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.arukikata.co.jp` |
| Sitemap URL | `https://www.arukikata.co.jp/wp-sitemap-posts-webmagazine-2.xml` |
| Rendering | Static HTML — uses `requests` + `BeautifulSoup` (no Playwright) |
| Auth required | No |
| Rate limit | Implicit; add 0.5 s between article fetches |
| Source name | `arukikata` |
| Source ID format | `arukikata_{article_id}` from URL path number (e.g. `/webmagazine/362618/` → `arukikata_362618`) |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `arukikata_{article_id}` from URL path |
| `raw_title` | `<h1>` or `og:title` on article page |
| `start_date` | `<dt>`/`<dd>` structured block: `開催日時` / `日時` / `会期` label |
| `end_date` | End of date range in same block; `None` if single-day |
| `location_name` | `会場` / `場所` `<dd>` block |
| `location_address` | `住所` `<dd>` block; fallback to `location_name` |
| `raw_description` | Article body text |

## Title Filter (Dual-keyword — CRITICAL)

Only keep articles whose title matches **both** 東京 and 台湾 within 30 characters:

```python
_TOKYO_TAIWAN = re.compile(r"台湾.{0,30}東京|東京.{0,30}台湾", re.IGNORECASE)
```

This prevents ingestion of Taiwan travel articles, Taiwan restaurant guides (outside Tokyo), or global event roundups.

## Past-Event Report Filter

Skip recap articles identified by title keywords:

```python
_PAST_MARKERS = re.compile(r"レポート|レポ|報告|記録|アーカイブ|recap", re.IGNORECASE)
```

These are post-event write-ups, not future event announcements.

## Lookback Window

`LOOKBACK_DAYS = 90` applied on sitemap `<lastmod>` date — only process articles modified in the past 90 days. The sitemap contains up to 2605 entries; without this filter the scraper re-processes the full archive on every run.

## Sitemap Monitoring

```python
SITEMAP_URLS = [
    "https://www.arukikata.co.jp/wp-sitemap-posts-webmagazine-2.xml",
]
```

If articles stop appearing, check whether a new sitemap page has been added (e.g. `-3.xml`). The `-2.xml` page covers the most recent 2605 posts.

## Date Extraction

Event details are in structured `<dl>/<dt>/<dd>` blocks. Key labels:
- `開催日時` — primary event date/time
- `日時` — alternate label
- `会期` — multi-day exhibition period

Day-of-week annotations like `（土）` are stripped using `_DOW` regex before date parsing.

## Pending Rules

<!-- Added automatically by confirm-report -->
