---
name: artistcafe
description: Per-source rules for ArtistcafeScraper (artistcafe.jp)
applyTo: scraper/sources/artistcafe.py
---

# ArtistcafeScraper — Source-Specific Rules

## Platform Profile

| Item | Value |
|------|-------|
| Site URL | https://artistcafe.jp/event/ |
| Rendering | Server-side HTML (Playwright used for JS-heavy listing) |
| Auth | None |
| Rate limit | None observed |
| Source name | `artistcafe` |
| Source ID format | `artistcafe_{wp_post_id}` (e.g. `artistcafe_2340`) |
| Location | Fukuoka, Japan (Artist Cafe Fukuoka) |

## Field Mappings

| Event field | Selector / source |
|-------------|-------------------|
| `name_ja` | `a.text-article-list-title` (listing card) |
| `start_date` | `p.text-article-list-date` — regex `(\d{4})\.(\d{1,2})\.(\d{1,2})` |
| `source_url` | Detail page href from `a.text-article-list-title` |
| `source_id` | `artistcafe_{n}` from URL `/event/(\d+)` |
| `raw_description` | `<article>` on detail page; fallback `<body>` |

## Taiwan Relevance Filter

> **CRITICAL**: artistcafe.jp ignores `?keyword=` URL parameters entirely.
> Keyword filtering MUST be done in-scraper after visiting each detail page.

- `?keyword=台湾` returns the same 12 results as no keyword at all — verified 2026-05-05
- After fetching detail page, run `_is_taiwan(title + description)` before creating an Event
- Keywords: `台湾`, `Taiwan`, `台灣`, `臺灣`
- Expected pass rate: ~4/12 events (~33%) as of 2026-05

## Date Extraction

- Listing card shows `YYYY.MM.DD` format (e.g. `2026.04.18`)
- Regex: `(\d{4})\.(\d{1,2})\.(\d{1,2})` — handles single-digit months/days
- No time component; `start_date` is midnight of the event date

## Description Extraction

- **Use `article` selector** on detail page, NOT `body` — `body.inner_text()` captures
  navigation headers (`OPEN 11:00 - 19:00 アクセス アーティスト相談 …`) that pollute `raw_description`
- Fallback to `body` only if `article` element not found (count == 0)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Non-Taiwan events in DB | `?keyword=` ignored by site | Add/verify `_is_taiwan()` check in `_extract_cards` |
| `raw_description` is nav text | `body.inner_text()` instead of `article` | Use `DETAIL_CONTENT_SELECTOR = "article"` |
| 0 events found | `li.article-list` selector broken | Check site HTML; they may have redesigned |
| Page 2+ yields 0 events | Site only has 1 page of events (12 cards) | Normal — `MAX_PAGES=5` but stops at first empty page |

## Pending Rules

- Monitor if site adds more Taiwan-related content over time
- Sub-events (e.g. `artistcafe_2359_sub1`) were manually created in DB — these are NOT produced by the scraper and will remain deactivated unless created manually again
