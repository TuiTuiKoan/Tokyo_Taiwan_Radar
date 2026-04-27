---
name: oaff
description: "Platform rules, Taiwan filter, and date extraction for the 大阪アジアン映画祭 (OAFF) scraper"
applyTo: scraper/sources/oaff.py
---

# OAFF Scraper Skill

## Platform Profile

| Item | Value |
|------|-------|
| Site URL | https://oaff.jp/ |
| API / Rendering | WordPress REST API (`/wp-json/wp/v2/posts`) |
| Auth | None |
| Rate limit | Light — 0.3s sleep between posts |
| Source name | `oaff` |
| Source ID format | `oaff_{wp_post_id}` (WordPress integer post ID, stable) |
| Source URL | `https://oaff.jp/programs/{slug}/` |

## Taiwan Relevance Filter

Two-tier filter — either is sufficient:

1. **Slug pattern**: `re.search(r"tw\d+", slug, re.IGNORECASE)` — dedicated Taiwan section (e.g. `2025-tw01`, `2025expo-tw03`)
2. **Content keyword**: `台湾` or `taiwan` in title or first 500 chars of content

TAIWAN NIGHT events (`taiwan-night{year}expo`, `taiwan-night{year}`) use keyword filter.
Competition section Taiwan films (e.g. `2025-co03`) use keyword filter.

## Field Mappings

| Event field | Source | Notes |
|-------------|--------|-------|
| `source_id` | `oaff_{post["id"]}` | WordPress integer ID |
| `source_url` | `https://oaff.jp/programs/{slug}/` | Always stable |
| `name_ja` | `title.rendered` stripped of `(NN) ` prefix | e.g. "(51) 晩風" → "晩風" |
| `description_ja` | Synopsis paragraph from content | Before `上映予定` block |
| `raw_title` | `title.rendered` as-is | Keep the `(NN) ` prefix |
| `raw_description` | `開催日時: …\n\n` + full `content` text (800 chars) | |
| `start_date` | First date found in content | See date formats below |
| `location_name` | Venue from first screening line | Fallback: `大阪中之島美術館` |
| `location_address` | `大阪府大阪市北区中之島4丁目3-1` | Hardcoded (primary venue) |
| `is_paid` | `True` | All OAFF screenings require tickets |
| `category` | `["movie"]` | All entries are film screenings |

## Date Extraction

Three formats encountered across festival editions:

| Pattern | Example | Regex |
|---------|---------|-------|
| Full date | `2025年3月21日（金）18:50` | `(\d{4})年(\d{1,2})月(\d{1,2})日` |
| M月D日 | `3月15日（土）10:10／会場名` | `(\d{1,2})月(\d{1,2})日[（(]…[）)]\s*(\d{2}:\d{2})` |
| M/D | `3/4(月) 13:00　シネ・リーブル梅田` | `(\d{1,2})/(\d{1,2})[（(]…[）)]\s*(\d{2}:\d{2})` |

**Year inference**: Extracted from slug prefix via `re.search(r"(\d{4})", slug)`.
- `2025-tw01` → 2025  
- `2025expo-tw03` → 2025  
- `taiwan-night2025` → 2025 (trailing match)  

## Festival URL Patterns

| Edition | URL | Period |
|---------|-----|--------|
| OAFF main (March) | `https://oaff.jp/oaff{YEAR}/programs/` | February–March |
| OAFF expo (Aug–Sep) | `https://oaff.jp/oaff{YEAR}expo/programs/` | August–September |

**The WP REST API returns all posts from all editions** via the `categories=8` filter — no need to detect year URLs separately.

## Lookback Window

`LOOKBACK_DAYS = 45` — include events with `start_date >= today - 45 days`.

When the festival is not running (e.g. April–July), the scraper correctly returns 0 events.
The 2026 main festival is typically announced in December–January; check by running the scraper then.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 0 events returned | Festival season not active | Expected — wait for program announcement |
| `no-date` events | New date format introduced | Add new regex to `_parse_date()` |
| Wrong year on M月D日 | Slug pattern changed | Update `_infer_year()` regex |
| Venue falls back to default | New venue not matching regex | Check delimiter in `_extract_venue()` |
| Duplicate source_id | WP returns same post twice | Handled by `dedup_events()` in base |

## Pending Rules

_Add future lessons here._
