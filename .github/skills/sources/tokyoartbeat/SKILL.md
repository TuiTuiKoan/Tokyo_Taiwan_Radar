---
name: tokyoartbeat
description: Platform rules and field mappings for the Tokyo Art Beat Taiwan events scraper
---

# tokyoartbeat — Source Skill

## Platform Overview

- **Name**: Tokyo Art Beat
- **URL**: <https://www.tokyoartbeat.com/events/search?query=%E5%8F%B0%E6%B9%BE>
- **Type**: Tokyo's largest art event aggregator
- **Rendering**: React JS rendering — **Playwright required**
- **Events/month**: ~5–15 Taiwan-related events

## Scraper Key

```
--source tokyo_art_beat
```

Class: `TokyoArtBeatScraper` → key auto-derived as `tokyo_art_beat` (NOT `tokyoartbeat`).

## Strategy

1. Load search results: `/events/search?query=台湾` (URL-encoded).
2. Collect event detail URLs from paginated results (up to `MAX_PAGES = 5`, ~30 events/page).
3. Pagination: append `?page=N` for pages 2+.
4. For each event URL, fetch the detail page with Playwright.
5. Filter: check Taiwan keywords against `title + body_text`.
6. **Date from URL**: Extract `YYYY-MM-DD` from the URL path — most reliable source.

## Field Mappings

| Field | Source |
|-------|--------|
| `source_id` | `tokyoartbeat_{slug_part}` where `slug_part` = URL path after `/events/-/` with `/` → `_` (max 120 chars) |
| `source_url` | Full event URL |
| `name_ja` | Event `<h1>` title on detail page |
| `start_date` | Extracted from URL: `/events/-/{slug}/{venue-slug}/{YYYY-MM-DD}` |
| `location_name` | Venue name from detail page |
| `location_address` | Venue address from detail page (if available) |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + body_text` |

## Date Extraction

Event URLs contain the start date:

```
/events/-/Chen-Wei-Exhibition/ota-fine-arts-7chome/2026-04-21
```

```python
_EVENT_URL_RE = re.compile(r"/events/-/[^/?#\s]+/[^/?#\s]+/(\d{4}-\d{2}-\d{2})")
```

This is more reliable than parsing date text from the detail page.

## Taiwan Filter

Server-side search for `台湾` returns broadly matching results. Apply client-side keyword filter on detail page content.

### TAIWAN_KEYWORDS

```python
["台湾", "Taiwan", "臺灣", "台灣", "台北", "台中", "台南", "高雄", "台日", "日台"]
```

## Known Issues / Edge Cases

- **Slow**: Playwright loads 5 search result pages + N detail pages. Expect 3–8 min for dry-run.
- **React rendering**: Wait for event cards to appear before collecting URLs.
- **slug_part max length**: 120 chars to avoid DB key overflow.
- **Exhibitions vs. events**: Tokyo Art Beat covers both single-day events and multi-day exhibitions. `end_date` should be set when the detail page shows an end date.
