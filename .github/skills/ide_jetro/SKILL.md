---
name: ide_jetro
description: Platform rules, Taiwan title filter, date extraction, and lookback window for the IDE-JETRO scraper
applyTo: scraper/sources/ide_jetro.py
---

# ide_jetro Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.ide.go.jp` |
| Listing URL | `https://www.ide.go.jp/Japanese/Event/Seminar.html` |
| Rendering | Static HTML — uses `requests` + `BeautifulSoup` (no Playwright) |
| Auth required | No |
| Rate limit | `REQUEST_DELAY = 1.0` s between detail-page fetches |
| Source name | `ide_jetro` |
| Source ID format | `ide-jetro_{YYMMDD}` from URL path (e.g. `/Japanese/Event/Seminar/250926.html` → `ide-jetro_250926`) |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `ide-jetro_{YYMMDD}` from `<a href>` path |
| `raw_title` | `og:title` meta tag on detail page, or `<h1>` |
| `start_date` | First `YYYY.MM.DD` occurrence in listing `<span class="date">` |
| `end_date` | Second date in range notation `YYYY.MM.DD〜YYYY.MM.DD`; `None` if single-day |
| `location_name` | IDE venue (usually 幕張メッセ or 研究所内) from body |
| `raw_description` | Detail page body text |

## Taiwan Title Filter

The listing contains hundreds of seminars; only keep items whose title contains `台湾`:

```python
if "台湾" not in item_title:
    continue
```

This is the primary relevance gate. Do not widen it — IDE-JETRO events are academic/business and the false-positive rate for non-Taiwan content is high.

## Lookback Window

`LOOKBACK_DAYS = 180` — only ingest events whose `start_date` is within the past 180 days or any future date. The listing page accumulates past years; without this cutoff the scraper re-ingests stale records on every run.

## Date Format

Listing page dates are `YYYY.MM.DD` (dotted, ASCII digits):

```
Single : 2025.09.26 (金曜)
Range  : 2025.11.25 (火曜)〜2026.03.13 (金曜)
```

`_parse_date_dotted(s)` extracts the first `YYYY.MM.DD` occurrence.

## Source Overlap Note

The `/Sympo/` page mirrors the `/Seminar/` listing — 100% overlap. Only scrape `Seminar.html`; do not add the Symposia URL to avoid duplicate ingestion.

## Pending Rules

<!-- Added automatically by confirm-report -->
