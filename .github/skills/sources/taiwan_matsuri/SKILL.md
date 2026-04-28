---
name: taiwan_matsuri
description: Platform rules, link discovery, date/venue extraction for the 台湾祭（taiwan-matsuri.com）scraper
applyTo: scraper/sources/taiwan_matsuri.py
---

# taiwan_matsuri Scraper Skill

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://taiwan-matsuri.com |
| Rendering | Static HTML (no JavaScript required) |
| Auth | None |
| Rate limit | Polite — `time.sleep(1.0)` between detail pages |
| Source name | `taiwan_matsuri` |
| Source ID format | `taiwan_matsuri_{YYYYMM}-{slug}` (e.g. `taiwan_matsuri_202604-skytree`) |

## Event Discovery

- Homepage lists all past and present events as `<a href="/YYYYMM-slug/">` links.
- Link text includes status prefix: `開催中` (active) or `イベント終了` (ended).
- **Skip links whose text contains `終了`** — those events have ended; re-scraping them wastes requests.
- After dedup, there are typically 3–5 active events at any given time.

## Field Mappings

| Event field | Source in page | Notes |
|-------------|---------------|-------|
| `name_ja` | Line containing `台湾祭` in first 20 text lines | Falls back to `<title>` tag |
| `start_date` / `end_date` | `●開催期間：YYYY年M月D日〜M月D日` block | Fallback: scan all lines for date pattern |
| `location_name` | `●場所：<name>` label | Strip trailing `（address）` |
| `location_address` | `（都道府県...）` parenthetical after `location_name` | Falls back to `location_name` |
| `business_hours` | `●営業時間：【平日】...【土日祝】...` | Joins `【...】` blocks with `\u3000` |
| `official_url` | = `source_url` (detail page IS the organiser page) | |
| `is_paid` | Hardcoded `False` | Admission confirmed free on all pages |
| `category` | `["lifestyle_food", "tourism"]` | |

## Geographic Scope

台湾祭 is held nationwide: Tokyo, Gunma, Kumamoto, Fukuoka, Nara, Shimane and more. **Never add a regional filter.** The project covers 全日本.

## Date Extraction Notes

The date line format varies by event:
- `2026年4月4日(土)〜5月31日(日)` — most common
- `2026/04/04〜05/31` — slash format occasionally used
- Regex in `_parse_dates()` handles both. Cross-year ranges (end_year ≠ start_year) are handled by capturing the optional `YYYY/` prefix in pattern 2.

## Taiwan Relevance

All events on this site are Taiwan-themed by definition — no filter needed.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| New events not appearing in DB | Only dry-run was executed after fix | Run `python main.py --source taiwan_matsuri` (non-dry-run) |
| Events from Gunma / Kyushu missing | Regional keyword filter re-added | Remove any `_TOKYO_KANTO_KEYWORDS` or similar filter |
| `No title found` warning | Detail page structure changed | Check first 20 text lines; update `skip_patterns` |
| Date parsing returns `None` | New format in `●開催期間` | Add new case to `_parse_dates()` |

## Pending Rules
<!-- Add rules discovered during future bug fixes here -->
