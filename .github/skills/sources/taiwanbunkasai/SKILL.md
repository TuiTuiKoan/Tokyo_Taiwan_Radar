---
name: taiwanbunkasai
description: "Platform rules, single-page event extraction, and date parsing for the 台湾文化祭 (taiwanbunkasai.com) scraper"
applyTo: scraper/sources/taiwanbunkasai.py
---

# 台湾文化祭 (taiwanbunkasai.com) Scraper

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://taiwanbunkasai.com/ |
| Rendering | Static HTML (requests + BeautifulSoup) |
| Auth | None |
| Rate limit | 1 request total (single-page site) |
| Source name | `taiwanbunkasai` |
| Source ID format | `taiwanbunkasai_{YYYY}_{MM:02d}` (one event per announcement month) |
| Events per year | ~3 (KITTE ×2, 中野 ×1) — but only the next event is shown at any time |

## Field Mappings

| Event field | Source |
|-------------|--------|
| `name_ja` | `<title>` tag (e.g. "台湾文化祭") |
| `start_date` | Regex on `YYYY年M月D日` in page text — first occurrence in 開催日 block |
| `end_date` | Max day number in the same date range (same month assumed) |
| `location_name` | Text after `● 会場` label, stripped of map notes |
| `location_address` | Same as `location_name` (site does not provide a separate address) |
| `raw_description` | Text block between `出店概要` and `開催実績` headings |

## Single-Page Site Notes

- Only ONE upcoming event is shown on the homepage at any given time.
- After an event passes, the page is updated for the next event.
- `source_id` uses `{year}_{month:02d}` to ensure uniqueness across events:
  - Same year but different months = different events = different source_ids
  - Scraper will create a new DB row automatically for each new event

## Date Extraction

```
● 開催日
2026年6月26日（金）・27日（土）・28日（日）
```

- `_START_DATE_RE` captures `(20\d{2})年(\d{1,2})月(\d{1,2})日` → year, month, start_day
- End day: max of all `\d{1,2}日` matches in the next 200 chars (same month assumed)
- If only one day listed, `end_date = start_date`

## Venue Extraction

```
● 会場
「中野区役所 ソトニワ＋ナカノバ」＆
「四季の森公園　芝生エリア＋イベントエリア」
```

- `_VENUE_RE` captures text block after `● 会場` until next `●` bullet or end
- Fallback: extract `「…」` quoted venue names (at most 2), join with ` / `
- Strip trailing map/note text (`会場地図拡大`, `×`, etc.)

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `start_date` null | Page layout changed; `● 開催日` removed | Inspect page text; update `_START_DATE_RE` or add new pattern |
| 0 events returned | Site is between events (post-event, pre-announcement) | Expected seasonal gap — not a bug |
| Duplicate source_id | Two events in the same year-month | Extend source_id to include `_{DD}` start day |
| Venue is truncated | `● 会場` block parsing hit map note early | Adjust `_VENUE_RE` or `re.sub` cleanup pattern |

## Pending Rules

_(Add rules here as edge cases are discovered in production.)_
