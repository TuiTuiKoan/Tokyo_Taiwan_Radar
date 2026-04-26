---
name: moonromantic
description: Platform rules and field mappings for the 月見ル君想フ (MoonRomantic) live venue scraper
---

# moonromantic — Source Skill

## Platform Overview

- **Name**: 月見ル君想フ (Tsukimi Ru Kimi Omou / MoonRomantic)
- **URL**: <https://www.moonromantic.com/>
- **Type**: Live music venue (Minami-Aoyama, Tokyo)
- **Location**: 東京都港区南青山4-9-1 B1F
- **Rendering**: Wix JS rendering — **Playwright required**
- **Events/month**: ~1–2 Taiwan-related events

## Scraper Key

```
--source moon_romantic
```

Class: `MoonRomanticScraper` → key auto-derived as `moon_romantic` (NOT `moonromantic`).

## Strategy

1. Build monthly schedule URLs: `https://www.moonromantic.com/allevents/categories/YYYY-MM`
2. Scrape current month + `MONTHS_AHEAD = 3` future months (4 pages total).
3. Collect `/post/{slug}` links from each schedule page.
4. For each event post, fetch the detail page with Playwright.
5. Filter: check Taiwan keywords against `title + body_text`.
6. Extract date from title prefix `"YYYY.MM.DD | Event Title"`.

## Field Mappings

| Field | Source |
|-------|--------|
| `source_id` | `moonromantic_{slug_clean}` (URL slug, max 80 chars, alphanumeric + hyphens + underscores) |
| `source_url` | Full post URL, e.g. `https://www.moonromantic.com/post/260510` |
| `name_ja` | Post title from `<h1>` (includes date prefix) |
| `start_date` | Parsed from title prefix `"YYYY.MM.DD | ..."` |
| `location_name` | Always `"月見ル君想フ"` (hardcoded) |
| `location_address` | Always `"東京都港区南青山4-9-1 B1F"` (hardcoded) |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + body_text` |

## Date Parsing

Title format: `"2026.05.10 (日) DSPS Japan Tour"`

```python
_TITLE_DATE_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})")
```

Parses `YYYY.MM.DD` from start of title.

## Taiwan Filter

Most events at this venue are Japanese indie — Taiwan filter is critical.

### TAIWAN_KEYWORDS

```python
[
    "台湾", "Taiwan", "臺灣", "台灣",
    "台北", "高雄", "台中", "台南",
    "台日", "日台",
    # Label / promoter
    "BIG ROMANTIC", "大浪漫",
    # Frequently touring Taiwan artists
    "DSPS", "VOOID", "Andr", "Sunset Rollercoaster",
    "日落飛車", "告五人", "魚丁糸", "ØZI", "Elephant Gym", "大象體操",
]
```

## Known Issues / Edge Cases

- **Slow**: Playwright loads 4 monthly pages + N individual post pages. Expect 2–5 min for dry-run.
- **Wix lazy-loading**: Schedule pages may need `page.wait_for_selector("a[href*='/post/']")`.
- **Post URL skips**: `/post/announcement` and `/post/_system` are filtered out.
- **Slug max length**: 80 chars (truncated if longer) to avoid DB key overflow.
