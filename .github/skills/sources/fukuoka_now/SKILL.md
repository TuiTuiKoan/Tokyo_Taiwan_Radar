---
name: fukuoka-now
description: Scraper rules for Fukuoka Now event calendar (fukuoka-now.com/en/event/)
applyTo: scraper/sources/fukuoka_now.py
---

# Fukuoka Now Source Skill

## Platform Profile

| Property | Value |
|----------|-------|
| Site URL | https://www.fukuoka-now.com/en/event/ |
| Rendering | Static HTML (WordPress) — **no Playwright needed** |
| Auth | None |
| Rate limit | None observed; 1 s delay between detail pages |
| Source name | `fukuoka_now` |
| Source ID format | `fukuoka_now_{slug}` (e.g. `fukuoka_now_taiwan-matsuri-2026`) |
| Original language | `en` (English-language media) |
| Region | 福岡市 / Fukuoka Prefecture |

## Field Mappings

| Event field | Source | Notes |
|-------------|--------|-------|
| `raw_title` | `.c-page-sub__content-title` (detail page) | Falls back to `.c-page-sub__guide-title` (card) |
| `raw_description` | `.c-content-main p` joined | Prepend `開催日時: YYYY年M月D日\n\n` |
| `start_date` | `time[datetime]` in `.c-event-date-detail__start` | ISO 8601 — always use detail page dates |
| `end_date` | `time[datetime]` in `.c-event-date-detail__end` | Optional; falls back to `start_date` |
| `source_url` | `a[href]` on the card | Full URL to detail page |
| `location_name` | Extracted from description body | Line containing "City Hall", "Fureai", "Tenjin", etc. |
| `location_address` | Same as `location_name` | No separate address field on Fukuoka Now |

## Taiwan Relevance Filter

Keywords applied to card title + tags + short description:
```python
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "Taiwanese", "臺灣"]
```

**Known annual Taiwan events on Fukuoka Now**:
- **台湾祭 in 福岡** (Taiwan Matsuri in Fukuoka) — held Jan/Feb each year at Fukuoka City Hall Fureai Hiroba. Started 2016; 10th anniversary in 2026.

## Date Extraction Notes

- ISO 8601 via `<time datetime="YYYY-MM-DD">` attribute — no parsing needed beyond `datetime.strptime(dt_str, "%Y-%m-%d")`.
- Listing page and detail page both have `time[datetime]`. **Always prefer the detail page** (more reliable, includes end date).
- Current active events (April 2026): no Taiwan events visible — 台湾祭 ended Feb 23, 2026. Scraper correctly returns 0 and will pick up next year's event when it is listed.

## Pagination

```
Page 1: https://www.fukuoka-now.com/en/event/
Page N: https://www.fukuoka-now.com/en/event/page/{N}/
```
- 10 events per page; stop when HTTP 404 or no `li.c-page-sub__guide-item` found.
- Typically 2–3 pages of active events.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| 0 events returned | Taiwan Matsuri season ended; no current Taiwan events | Normal — wait for next year's event |
| Venue is `None` | Description doesn't contain venue keywords | Extend `_extract_venue()` venue keyword list |
| Dates all None | WordPress changed `time[datetime]` class names | Verify selector on `.c-event-date-detail__start` |
| 404 on pagination | Fewer than expected pages | Normal — stop condition already handled |

## Pending Rules
