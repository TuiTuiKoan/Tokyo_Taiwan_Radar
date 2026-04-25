---
name: koryu
description: Platform rules, Taiwan-office filter, date extraction, and troubleshooting for the koryu scraper
applyTo: scraper/sources/koryu.py
---

# koryu Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.koryu.or.jp` |
| List URL | `https://www.koryu.or.jp/news/event/` |
| Rendering | DNN CMS, static HTML — Playwright used for consistency |
| Auth required | No |
| Rate limit | 1 s sleep between detail-page requests |
| Source name | `koryu` |
| Source ID format | `koryu_{itemid}` from URL query param `?itemid=NNNN` (stable) |

## Field Mappings

| Event Field | koryu Source |
|-------------|--------------|
| `source_id` | `koryu_{itemid}` from `?itemid=NNNN` in URL |
| `raw_title` | `<h2>` / `<h3>` heading on detail page |
| `start_date` | `日時：` / `時間：` field; fallback: DOW-qualified `月DD日（曜日）`; last resort: `YYYY年MM月DD日` |
| `end_date` | Same as `start_date` for single-day events; explicitly set at end of `_extract_event_fields` |
| `location_name` | `_extract_venue()` — regex `会場\s*\n?\s*(.{5,120})` |
| `location_address` | `_extract_location_address()` — `所在地/住所`; fallback to `_extract_venue()` result |
| `raw_description` | `main.inner_text()` of detail page |

## Taiwan-Office Filter (CRITICAL)

`koryu.or.jp` manages both **Japan** and **Taiwan** offices. Events organized by Taiwan offices must be **rejected** — they are held in Taiwan, not Tokyo.

The DNN CMS renders the office tag as part of the breadcrumb plain text:

```
お知らせイベント・セミナー情報台北
```

### Detection

```python
_TAIWAN_OFFICE_TAGS = {"台北", "台中", "高雄", "台南", "桃園", "新竹", "基隆", "嘉義"}

def _extract_office_tag(body_text: str) -> Optional[str]:
    m = re.search(r'イベント・セミナー情報\s*([\u4e00-\u9fa5]{1,6})', body_text)
    return m.group(1).strip() if m else None
```

In `_scrape_detail`: if `office_tag in _TAIWAN_OFFICE_TAGS` → return `None`.

**Never remove this check.** Without it, Taiwan-office events leak into the DB.

## Date Extraction Priority

koryu pages contain a publish date at the top of the body (`2026年4月20日`) that is NOT the event date. Use this priority order:

1. `日時：` field → labeled date (most reliable)
2. `時間：` field combined with nearest date context
3. DOW-qualified date: `5月16日（土）` (day-of-week confirms it is an event date)
4. **Last resort only**: generic `YYYY年MM月DD日` fallback (risks picking up publish date)

Always set `end_date = start_date` at the end of `_extract_event_fields` for single-day events.

## Location Extraction

- `_extract_venue()`: regex `会\s*場\s*\n?\s*(.{5,120})` — captures venue name.
- `_extract_location_address()`: regex `(?:所在地|住所|住　所)\s*\n?\s*(.{5,100})`.
- Fallback: if `location_address` is empty, use `venue` if available.
- When event page returns 404 (stale/deleted event): `main_text` contains a redirect message; both `_extract_venue` and `_extract_location_address` return `None` — this is acceptable.

## Dead Code Anti-Pattern

If you define a filter function (e.g. `_is_tokyo_venue()`), wire it up in `_scrape_detail` **immediately**. Unconnected utility functions have caused Taiwan-office events to bypass filters in the past.

## Pending Rules

<!-- Added automatically by confirm-report -->
