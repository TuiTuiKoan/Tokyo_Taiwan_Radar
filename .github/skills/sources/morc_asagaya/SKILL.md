---
name: morc_asagaya
description: Platform rules, false-positive prevention, and date extraction for the Morc阿佐ヶ谷 scraper
applyTo: scraper/sources/morc_asagaya.py
---

# Morc阿佐ヶ谷 Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://www.morc-asagaya.com> |
| Rendering | Static HTML (WordPress) — no JS required |
| Auth | None |
| Rate limit | 0.5 s delay between film pages |
| Source name | `morc_asagaya` |
| Source ID format | `morc_asagaya_{url-slug}` (slug = path segment after `/film/`) |

## Listing Strategy

1. Fetch two listing pages: `/film_date/film_now/` and `/film_date/film_plan/`
2. Collect all links matching `/film/[^/]+/$` (exclude `/film_date/` index pages)
3. Deduplicate by full URL
4. For each film page: fetch → remove `#tp_info` → Taiwan filter → extract

## Taiwan Relevance Filter

**Critical**: Every film page contains a site-wide INFORMATION notice section (`section#tp_info`) that includes a "台湾巨匠傑作選" banner. **Always call `soup.select('#tp_info')[...].decompose()` before applying keyword search**, otherwise all 24+ films produce false positives.

Keywords (applied after `#tp_info` removal):
`["台湾", "Taiwan", "臺灣", "金馬", "台北", "台中", "高雄"]`

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `<h1>` text |
| `raw_title` | same as `name_ja` |
| `source_id` | `morc_asagaya_{slug}` |
| `source_url` | film page URL |
| `start_date` | "上映日時" label → next sibling text or `<h2>` with M/D pattern |
| `end_date` | end of date range |
| `location_name` | `Morc阿佐ヶ谷` (fixed) |
| `location_address` | `東京都杉並区阿佐谷北2丁目12番21号 あさがやドラマ館2F` (fixed) |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction

Date text appears in two ways:

1. **"上映日時" label** → next sibling element → text like `4/24(金)〜4/30(木)`
2. **`<h2>` fallback** → regex `\d{1,2}/\d{1,2}` inside an h2 element

Pattern: `_DATE_RANGE_RE = r"(\d{1,2})/(\d{1,2})[^〜\n]*?(?:〜|~)(\d{1,2})/(\d{1,2})"`

Year inference: if `month < today.month - 3` → assume next year.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| All 24 films returned as Taiwan | `#tp_info` not removed before keyword search | Add `soup.select('#tp_info')[...].decompose()` before `get_text()` |
| `start_date` is None | Date text not found by "上映日時" label search | Check if site changed layout; add fallback h2 pattern |
| 0 events when Taiwan festival is running | Keywords not in film article text | Check if festival name changed; add new keyword |

## Pending Rules

<!-- Add source-specific lessons learned here -->
