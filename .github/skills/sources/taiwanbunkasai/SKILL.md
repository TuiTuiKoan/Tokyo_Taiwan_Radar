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
| `name_ja` | **Constructed**: `f"台湾文化祭{year}"` (NOT raw `<title>`) — year suffix needed for merger |
| `raw_title` | `<title>` tag (e.g. "台湾文化祭") |
| `start_date` | Regex on `YYYY年M月D日` in page text — first occurrence in 開催日 block |
| `end_date` | Max day number in the same date range (same month assumed) |
| `location_name` | Resolved from `_VENUE_MAP` keyword match |
| `location_address` | Resolved from `_VENUE_MAP` keyword match |
| `official_url` | `https://taiwanbunkasai.com/` |
| `is_paid` | Hardcoded `False` (入場無料, verified 2026-04-26) |
| `category` | `["lifestyle_food", "performing_arts", "senses"]` |
| `raw_description` | Text block between `出店概要` and `開催実績` headings |

## Venue Map (_VENUE_MAP)

| Keyword in 会場 text | location_name | location_address |
|---------------------|---------------|------------------|
| `中野` | 中野区役所・四季の森公園 | 東京都中野区中野4丁目8-1 |
| `KITTE` / `kitte` / `丸の内` | KITTE 丸の内 | 東京都千代田区丸の内2-7-2 |

Add new keywords when new venues appear.

## Duplicate Handling (CRITICAL)

**Rule**: iwafu (and arukikata) independently scrape the same event.

- `name_ja` MUST be `f"台湾文化祭{start_date.year}"` — iwafu uses 年份 suffix (e.g. "台湾文化祭2026").
  Raw `<title>` is "台湾文化祭" (no year) → similarity = 0.71 ← MERGER DOES NOT FIRE.
  With year: similarity = 1.000 → merger auto-deactivates iwafu version. ✓
- `merger.py` SOURCE_PRIORITY: `taiwanbunkasai=7`, `iwafu=11` → taiwanbunkasai always wins.
- After first run: iwafu version deactivated, its URL moved to `secondary_source_urls`.
- Subsequent iwafu scraper runs: blocked by `blocked_keys` (is_active=false). ✓

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
| Merger not firing vs iwafu | `name_ja` missing year suffix | Ensure `name_ja = f"台湾文化祭{start_date.year}"` |
| New venue not resolving | Keyword not in `_VENUE_MAP` | Add keyword + name + address to `_VENUE_MAP` |

## Pending Rules

_(Add rules here as edge cases are discovered in production.)_
