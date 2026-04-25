---
name: tuat_global
description: Platform rules, Taiwan keyword filter, date extraction, and venue handling for the 東京農工大学グローバルイノベーション研究院 scraper
applyTo: scraper/sources/tuat_global.py
---

# TUAT Global Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://www.tuat-global.jp/event/ |
| Type | Static HTML, WordPress |
| Auth | None |
| Rate Limit | None observed |
| Source Name | `tuat_global` |
| Source ID Format | `tuat_global_{wp_post_id}` (e.g. `tuat_global_10631`) |
| `--source` key | `tuat_global` |

TUAT Global Innovation Research Institute hosts public seminars featuring foreign researchers at Tokyo University of Agriculture and Technology campuses (府中市 and 小金井市 — both in Tokyo).

## Listing Page Structure

Events are listed as `<table>` elements (10 per page), newest-first.

```html
<table>
  <tbody>
    <tr><th>名称</th><td><a href="/event/NNNNN/">TITLE</a></td></tr>
    <tr><th>日時</th><td>2026.4.15（14：00～15：30）</td></tr>
    <tr><th>会場</th><td><p>東京農工大学 府中キャンパス 2号館 2階 2-22講義室</p><p>Zoom</p></td></tr>
  </tbody>
</table>
```

Pagination: `/event/page/N/` (N ≥ 2). Scraper stops at `MAX_PAGES = 3`.

## Taiwan Relevance Filter

Filter on **title only** — Taiwan researchers appear as `/ 国立陽明交通大学（台湾）` in the title.
Keywords: `["台湾", "Taiwan", "臺灣"]`.
Expected yield: ~1–3 Taiwan events per year.

## Field Mappings

| Event Field | Source |
|---|---|
| `name_ja` | `<a>` inside 名称 `<td>` |
| `start_date` | 日時 cell, parsed from `"YYYY.M.D（HH：MM～HH：MM）"` |
| `location_name` | First line of 会場 cell |
| `location_address` | All non-http lines of 会場 cell |
| `source_url` | `href` of the title link |
| `source_id` | `tuat_global_{post_id}` from URL |
| `is_paid` | `False` (all seminars are free and open) |
| `category` | `["academic", "taiwan_japan"]` |

## Date Extraction

Format: `"2026.4.15（14：00～15：30）"` or `"2026.3.2（15：00～17：00）"`

- Remove Japanese weekday characters `（月）（火）...` first
- Match `YYYY.M.D` for date
- Match `HH：MM～` for start time (full-width colon `：`)
- Falls back to midnight JST when no time found
- LOOKBACK_DAYS = 60 (skip events older than 60 days)

## Venue Handling

- Venue cell may contain multiple `<p>` tags (e.g. physical address + "Zoom")
- Keep all non-http lines joined by `\n` for `location_address`
- Use first line as `location_name`

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| 0 events found | Taiwan researcher not yet scheduled | Normal — check page manually |
| date parse fails | Unusual date format | Add format variant to `_parse_date()` |
| venue missing | Table row label changed | Check `th` text in browser |

## Pending Rules

- Verify whether event detail pages contain additional info not on the listing (e.g., abstract) and whether it's worth fetching them.
