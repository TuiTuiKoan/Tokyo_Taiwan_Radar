---
name: waseda_taiwan
description: Platform rules, event detection, date/venue extraction for the 早稲田大学台湾研究所 scraper
applyTo: scraper/sources/waseda_taiwan.py
---

# Waseda Taiwan Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://waseda-taiwan.com/ |
| Type | WordPress REST API |
| Auth | None |
| Rate Limit | None observed |
| Source Name | `waseda_taiwan` |
| Source ID Format | `waseda_taiwan_{wp_post_id}` (e.g. `waseda_taiwan_675`) |
| `--source` key | `waseda_taiwan` |

早稲田大学台湾研究所 holds lectures, symposia, and workshops at Waseda Campus (東京都新宿区西早稲田), ~1–2 events per month. **ALL events are Taiwan-related** — no keyword filter needed. Some posts are working papers, newsletters, or blog articles — these must be filtered out.

## Event Detection

Not all posts are events. Filter: post content must match `r'(?:日\s*時|開催日時|開催日)[：:：]'`.

Working papers, announcements, and blog entries do NOT have these date labels.

## Date Label Variants Encountered

| Variant | Example |
|---|---|
| `日時：YYYY年M月DD日（曜日）` | `日時：2026年4月25日（土）10：30～15：55` |
| `日 時：YYYY年M月DD日(曜日)` | `日 時：2026年4月13日(月) 18:00-20:30` (space inside 日時) |
| `日時：YYYY/M/DD（曜日）` | `日時：2026/1/24（土）14:30〜18:00` |
| `開催日時：YYYY年M月DD日` | `開催日時：2026年2月11日（水・祝）13:30〜17:00` |

**Critical**: DOW removal must replace with `" "` (space), not `""` (empty). Otherwise `YYYY/M/DD（土）HH:MM` becomes `YYYY/M/DDHH:MM` with no separator.

## Venue Label Variants

| Variant | Example |
|---|---|
| `場所：` | `場所：早稲田大学早稲田キャンパス14号館505教室` |
| `場 所：` | `場 所：早稲田大学・井深大記念ホール（東京都新宿区西早稲田1-20-14）` |
| `会場：` | `会場：早稲田大学29-7号館211教室` |
| `開催場所：` | `開催場所：早稲田大学早稲田キャンパス3号館606号室` |

Regex: `r"(?:場\s*所|会\s*場|開催場所)"` handles all variants.

## Field Mappings

| Event Field | Source |
|---|---|
| `name_ja` | Post `title.rendered` (HTML stripped) |
| `start_date` | Content: date label variants above |
| `location_name` | Venue field, first part (before full address) |
| `location_address` | `東京都...` prefix extracted if present, else venue |
| `source_url` | Post `link` |
| `source_id` | `waseda_taiwan_{post_id}` |
| `is_paid` | `False` (all events free, academic) |
| `category` | `["academic", "taiwan_japan"]` |

## Address Extraction

Regex `r"(東京都[^\s]{5,60})"` on the venue string extracts the full address when given. Strip trailing `）` characters after extraction.

## Stop Labels for `_extract_after_label`

`使用言語`, `言語`, `プログラム`, `定員`, `申込`, `主催`, `共催`, `講師`, `コメンテーター`, `司会`, `報告者`, `タイトル`, `■`, `●`, `※`, `http`

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Invalid date: 'YYYY/M/DDHH:MM'` | DOW removal with `""` instead of `" "` | Replace DOW with `" "` |
| Working paper posts scraped | Event detection too loose | Ensure `_EVENT_MARKERS` regex requires colon after label |
| `location_address` has trailing `）` | Regex captured closing bracket | Use `.rstrip("）)")` after extraction |
| 0 events | Dry-run within LOOKBACK_DAYS of a gap | Normal; check waseda-taiwan.com manually |

## Pending Rules

- Monitor whether `開催場所：` label becomes more common vs `場所：`/`会場：`.
