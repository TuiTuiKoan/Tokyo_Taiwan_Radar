---
name: tokyocity_i
description: Platform rules, date extraction, fixed venue, and Taiwan filter for the 東京シティアイ scraper
applyTo: scraper/sources/tokyocity_i.py
---

# 東京シティアイ Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.tokyocity-i.jp` |
| List URL | `https://www.tokyocity-i.jp/event/` |
| Rendering | WordPress — static HTML, **no Playwright sessions required between pages** |
| Auth required | No |
| Rate limit | 1 s sleep between detail pages (`_PAGE_DELAY = 1.0`) |
| Source name | `tokyocity_i` |
| Source ID format | `tokyocity_i_{post_id}` (numeric WordPress post ID from `/event/{id}/`) |

## Platform Overview

東京シティアイ is a tourist information center at KITTE B1F, Marunouchi, Tokyo.
It hosts regional PR events, exhibitions, and craft fairs. Taiwan-themed events appear ~2–5 times per year (台湾フェア, 台湾夜市, 台湾食文化展, etc.).

**All events are held at the same physical location**: KITTE 地下1階, 東京都千代田区丸の内2-7-2.

## Page Structure

### Event List Page (`/event/`)

- Paginated via `/event/page/{N}/` (typically 1–3 pages for active events)
- Each event: `article section a[href*="/event/NNNN/"]` — link wraps the card
  - Title: `<p>` inside the link
  - Date: `<dd class="col">` (may have year typos — use detail page dates instead)
  - Status tag: `<dt class="col-auto tag event_tag"><span>開催中|開催予定</span></dt>`
- Pagination check: look for `a[href*="/event/page/{N+1}/"]`

### Event Detail Page (`/event/{id}/`)

- Title: `h2.cap-lv1`
- Info table: `table.normal-table tbody tr` → `<th>` = label, `<td>` = value
  - Labels: `期間`, `時間`, `場所`, `主催`, `共催`, `公式サイト`, `お問い合わせ`
- The `<h1>` always reads `"イベント"` — use `h2.cap-lv1` for the actual title
- Inner text rendering: table cells appear as label on one line, value on next line

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `tokyocity_i_{post_id}` from `/event/{ID}/` |
| `raw_title` | `h2.cap-lv1` inner text |
| `start_date` | `期間` row from detail table; time from `時間` row |
| `end_date` | End of range in `期間`; falls back to `start_date` for single-day events |
| `location_name` | `場所` row value; fallback: `"東京シティアイ"` |
| `location_address` | Always `"東京都千代田区丸の内2-7-2 KITTE地下1階"` (fixed venue) |
| `is_paid` | `False` — all Tokyo City i events are **free admission** |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + article.inner_text()` |
| `original_language` | `"ja"` |

## Taiwan Relevance Filter

Apply to **card title** before loading detail page (fast reject), then recheck on full page body:

```python
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
```

0 Taiwan events returned = **expected and correct** when no Taiwan events are currently active. Do NOT treat 0 results as a scraper failure.

## Date Parsing (`_parse_date_cell`)

Input formats from `期間` row:
- `"2026/4/12（日）"` → single day
- `"2026/4/21（火）～ 5/6（水）"` → same-year range (infer year from start)
- `"2026/4/21（火）～ 2026/5/6（水）"` → explicit-year range

**Year-typo warning**: The listing page date may have year typos (e.g., `2026/5/8（金）～2025/5/10（日）`). Always use `期間` from the detail page table — it is the authoritative source.

## Fixed Venue

All events are held at the same location. When `場所` is absent from the detail table (rare), fall back to:

```python
_DEFAULT_LOCATION_NAME    = "東京シティアイ"
_DEFAULT_LOCATION_ADDRESS = "東京都千代田区丸の内2-7-2 KITTE地下1階"
```

Never infer the address from the `場所` row when the row contains a room/zone name
(e.g., `ＫＩＴＴＥ地下1階 東京シティアイパフォーマンスゾーン`) — use the fixed address constant regardless.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events | No current Taiwan events | Expected — check `is_active` count |
| `start_date` null | `期間` row absent or format changed | Inspect `_extract_table` output; add new format |
| Year typo in `end_date` | Listing-page date used | Ensure detail-page `期間` is the source |
| Duplicate events | Same event re-listed with new ID | Ensure `source_id` uses URL's numeric post ID |
| `is_paid = True` | Incorrectly inferred | All Tokyo City i events are free — hardcode `False` |

## Pending Rules

<!-- Added automatically by confirm-report -->
