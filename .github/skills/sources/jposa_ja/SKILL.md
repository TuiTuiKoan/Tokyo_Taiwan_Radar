---
name: jposa_ja
description: Platform rules, RSS feed structure, event filter, and date extraction for the jposa_ja (台北駐大阪経済文化弁事処) scraper
applyTo: scraper/sources/jposa_ja.py
---

# 台北駐大阪経済文化弁事処 Scraper — Platform Reference

The Osaka TECO posts news and event reports on a WordPress-based CMS.
Most posts are diplomatic visit reports; cultural event posts occur ~1–3 per month.

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://www.roc-taiwan.org/jposa_ja/ |
| API/Rendering | RSS + static HTML (no Playwright needed) |
| Auth required | No |
| Rate limit | Not documented; 0.3 s polite delay is sufficient |
| Source name | `jposa_ja` |
| Source ID format | `jposa_ja_{post_id}` e.g. `jposa_ja_46480` |

## Site Architecture

- Built on WordPress 4.3.5 (detected from RSS generator tag)
- Posts are rendered as fully static HTML — `requests` + `BeautifulSoup` work without JS
- Category RSS feeds: `https://www.roc-taiwan.org/jposa_ja/category/<encoded>/feed/`
- Available categories relevant to cultural events:
  - `%e6%94%bf%e5%8b%99` = 政務 (political / activities)
  - `%e6%96%87%e6%95%99` = 文教 (culture / education)
- WordPress REST API is disabled (`/wp-json/` returns 404)
- RSS paginates via `?paged=N`; each page returns 10 items newest-first

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `jposa_ja_{post_id}` — numeric ID from `/post/NNNNN.html` URL |
| `source_url` | `<link>` in RSS item |
| `raw_title` | `<title>` CDATA in RSS item |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + body text (first 3000 chars) |
| `start_date` | Extracted from body (see Date Extraction) |
| `end_date` | Same as `start_date` (single-day default) |
| `location_name` | Extracted from `会場：` / `開催場所：` label |
| `original_language` | `"ja"` |

## Event Filter

Two-layer filter applied to each RSS item title **before** fetching detail pages:

1. **Must match** `_EVENT_KW`: `上映会|展示会|展覧会|公演|コンサート|フェス|イベント|講演会|セミナー|映画|音楽祭|文化祭|台湾祭|…`
2. **Must NOT match** `_SKIP_KW`: `の表敬訪問を受ける$|の訪問を受ける$|と面会$|による表敬訪問$|…`

Without these filters, ~90% of posts are diplomatic visit recaps (外交拜会), not public events.

## Date Extraction Notes

Priority order in `_extract_date_from_body()`:

1. **Labeled field**: `日時：` / `開催日時：` → extract `YYYY年MM月DD日`
2. **Full-year kanji date** in body: `2026年4月11日` — prefer date within ±30 days of pubDate
3. **Month-day only**: `4月11日（曜）` → infer year from pubDate
4. **Fallback**: RSS `<pubDate>` (accurate for same-day recap posts; the office posts after the event)

**Note**: Same-day recap posts (処長が出席した等) use the publish date as a reasonable proxy for the event date, since the office typically publishes the recap the same day or the day after.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events found | No event posts in the lookback window — normal for this source | Increase `LOOKBACK_DAYS` or check RSS manually |
| Events missing | `_SKIP_KW` too aggressive | Check title against the regex; relax if needed |
| date = publish date | Body has no explicit date label; normal for recap posts | Acceptable — the event occurred on or near pubDate |
| Import error | `XMLParsedAsHTMLWarning` not suppressed | Add `warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)` at module top |

## Pending Rules

<!-- Added automatically by confirm-report -->
