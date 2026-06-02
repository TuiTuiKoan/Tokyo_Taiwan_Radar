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

### Structured fields required from detail page

For seminar pages, scraper must parse heading-based sections in detail HTML and map them explicitly:

| Detail section | Target field | Rule |
|---|---|---|
| `開催日程` | `business_hours` | extract time range (`HH:MM〜HH:MM` or `HH時MM分〜HH時MM分`) |
| `会場` | `location_name` | keep venue text; online webinars should stay `オンライン` |
| `主催` | `organizer` | use exact text from section block |
| `講師・プログラム` table | `performers` (via annotator) | collect speaker names from speaker column and inject into `raw_description` |

Do not rely on one generic paragraph-only description. If these sections are not parsed, front-end detail pages lose organizer/speaker/hours.

## IDE CMS Block Structure Guard

IDE pages are rendered with nested blocks (`pbNested`, `paragraph`, `table-basic`) after `<h4>` headings. Traditional sibling-only scraping can return empty strings even when content exists.

Required pattern:

1. Locate heading (`開催日程`, `会場`, `主催`, `講師・プログラム`).
2. Find the first nested content block after that heading (`div` with class containing `pbNested|paragraph|table-basic`).
3. Extract plain text / table cells from that block.

When this guard is violated, typical symptoms are:

* `business_hours = null`
* `organizer = null`
* `performer(s) = null`

for events that clearly have these fields on the source page.

## Raw Description Structure Rule

Always prepend structured lines before free-text summary when values exist:

* `会場: ...`
* `主催: ...`
* `時間: ...`
* `講師: ...`

This ensures annotator can deterministically recover organizer and performer fields.

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
