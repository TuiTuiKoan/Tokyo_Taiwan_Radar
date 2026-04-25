---
name: jats
description: Platform rules, WP API filtering, and date/venue extraction for the 日本台湾学会 (JATS) scraper
applyTo: scraper/sources/jats.py
---

# JATS Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://jats.gr.jp/ |
| Type | WordPress REST API |
| Auth | None |
| Rate Limit | None observed |
| Source Name | `jats` |
| Source ID Format | `jats_{wp_post_id}` (e.g. `jats_7410`) |
| `--source` key | `jats` |

JATS (日本台湾学会 / Japan Association for Taiwan Studies) is an academic society based at 東京大学東洋文化研究所 (文京区). It holds 定例研究会（関東）monthly at Tokyo universities (Waseda, Tokyo, Hosei) and an annual 学術大会. **ALL events are Taiwan-related** — no keyword filter needed.

## WP REST API

- Base: `https://jats.gr.jp/wp-json/wp/v2/posts`
- Category 6 (`taikai-tokyo`, 定例研究会Tokyo) — 226 posts
- Category 13 (`taikai-2`, 学術大会) — 21 posts (annual conference)

## Post Types in Category 6

Two types share the same category — only scrape the structured detail type:

| Type | URL Pattern | Content | Action |
|---|---|---|---|
| Announcement | `/taikai-tokyo/kantoNNN/` | Just says "学会ブログに掲載しました" | **SKIP** |
| Structured detail | `/taikai/tokyoNNN` | Has `日時`, `場所`, `プログラム` | **SCRAPE** |

Filter: `re.search(r"/taikai/tokyo\d+$", link)` — only structured detail posts.

## Field Mappings

| Event Field | Source |
|---|---|
| `name_ja` | Post `title.rendered` (HTML stripped) |
| `start_date` | Content: `日時 YYYY年M月DD日（曜日）HH:MM-HH:MM` |
| `location_name` | Content: `場所 VENUE` (stop at `■`, `※`, `http`, `プログラム`) |
| `location_address` | Same as `location_name` |
| `source_url` | Post `link` |
| `source_id` | `jats_{post_id}` |
| `is_paid` | `False` (academic seminars, free) |
| `category` | `["academic", "taiwan_japan"]` |

## Date Extraction

Format: `日時 2026年4月25日（土）10:30-16:00 （JST）`

- Label `日時` (no colon) followed by a space, then date
- Remove DOW `（土）` with `re.sub(r"（[月火水木金土日・祝）]+）", "", raw)`
- Remove `（JST）` annotation
- Match `YYYY年M月DD日` for date
- Match `HH:MM` (ASCII colon) for start time

## Stop Labels for `_extract_after_label`

`■`, `※`, `●`, `http`, `プログラム`, `言語`, `定員`, `申込`, `主催`

Single-char stops (`■`, `●`, `※`) need `\s+CHAR` not `\s+CHAR[\s：:]`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Announcement posts scraped | URL filter too loose | Ensure `_DETAIL_URL_RE = re.compile(r"/taikai/tokyo\d+$")` |
| `location_name` too long (includes URL) | Stop label not matching | Check `http` is in `_STOP_LABELS` with single-char rule |
| `start_date` = midnight | No time in post | Normal for some posts; date is still correct |

## Pending Rules

- Consider adding category 13 (学術大会) if annual conference is not covered by Peatix.
