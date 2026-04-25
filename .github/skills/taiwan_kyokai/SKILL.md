---
name: taiwan_kyokai
description: Platform rules, date extraction, Tokyo venue filter, and troubleshooting for the 台湾協会 scraper
applyTo: scraper/sources/taiwan_kyokai.py
---

# taiwan_kyokai Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://taiwan-kyokai.or.jp` |
| News URL | `https://taiwan-kyokai.or.jp/news/` |
| Rendering | Playwright (`sync_playwright`) |
| Auth required | No |
| Source name | `taiwan_kyokai` |
| Source ID format | `taiwan_kyokai_{slug}` from URL slug (stable) |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `taiwan_kyokai_{slug}` from URL path |
| `raw_title` | `<h1>` / article heading |
| `start_date` | `日時：` / `日　時：` label on detail page |
| `end_date` | Extracted from same label; defaults to `start_date` if single-day |
| `location_name` | Venue field on detail page |
| `location_address` | Same as `location_name` if no separate address field |
| `raw_description` | Full article body text |

## Event Detection

Not all pages under `/news/` are events. A page is treated as an event only if it contains a `日時：` / `日　時：` field. Articles without this field are skipped.

## Tokyo Venue Filter

Venue must contain at least one `_TOKYO_MARKERS` entry:

```python
_TOKYO_MARKERS = [
    "東京", "港区", "千代田区", "新宿区", "渋谷区", "中央区", "台東区",
    "文京区", "豊島区", "品川区", "目黒区", "江東区", "墨田区", "荒川区",
    "足立区", "葛飾区", "江戸川区", "北区", "板橋区", "練馬区", "杉並区",
    "世田谷区", "大田区", "中野区",
]
```

Exception: if no venue is present in the body but the title contains event keywords, keep the event (annotator will resolve).

## Date Formats

The site uses a mix of standard and imperial year formats:

```
2025年10月25日（土曜日）          ← standard Gregorian
令和8（2026）年４月12日（日）      ← Reiwa era with Gregorian in parentheses
2026年5月16日                     ← no day-of-week
```

`_convert_gengo(year_str, era)` maps imperial era names to Gregorian offsets:

```python
_GENGO = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911}
```

Single-day rule: `end_date = start_date` — all events are single-day ceremonies or lectures.

## Content Scope

All content on `taiwan-kyokai.or.jp` is Taiwan-related — no relevance gate needed beyond the Tokyo venue filter.

## Pending Rules

<!-- Added automatically by confirm-report -->
