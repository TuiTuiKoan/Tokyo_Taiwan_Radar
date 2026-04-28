---
name: gguide_tv
description: Platform rules, API authentication, date parsing, and Taiwan relevance filtering for the 番組表Gガイド (bangumi.org) TV program scraper
applyTo: scraper/sources/gguide_tv.py
---

# 番組表Gガイド (bangumi.org) Scraper — SKILL.md

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://bangumi.org> |
| API/Rendering | 2-step HTTP (static HTML fragment) — no Playwright required |
| Auth | None — session cookie obtained from Step 1 GET |
| Rate limit | Not published; use 0.3–0.5 s sleep between requests |
| Source name | `gguide_tv` |
| Source ID format | `gguide_{ebisId}` (e.g. `gguide_AlhwDA0YgAE`) |
| Official source | 番組表.Gガイド（放送局公式情報） |

## API Flow

```
Step 1: GET https://bangumi.org/search/?q={kw}
  → sets _ggm-web_session cookie (required for Step 2)

Step 2: GET https://bangumi.org/fetch_search_content/?q={kw}&type=tv
  Headers: Referer: https://bangumi.org/search/?q={kw}
  → returns HTML fragment (no page shell)

Step 3 (per item): GET https://bangumi.org/tv_events/{ebisId}
  → static HTML detail page with synopsis
```

## HTML Selectors (list fragment)

| Data | Selector | Notes |
|---|---|---|
| Program list | `ul.list-style-1 li.block` | Skip `li.ads` |
| Genre | `.box-2 p` [0] | e.g. `バラエティ`, `ドキュメンタリー／教養` |
| Title | `.box-2 p` [1] | May contain accessibility emoji (🈑🈞🈓) |
| Schedule | `.box-2 p` [2] | `"4月29日 水曜 12:00　テレ東"` |
| ebisId | `a.js-logging[data-content]` → JSON → `.ebisId` | Stable across runs |

## Field Mappings

| Event field | Source | Notes |
|---|---|---|
| `source_id` | `gguide_{ebisId}` | Stable dedup key |
| `source_url` | `https://bangumi.org/tv_events/{ebisId}` | |
| `name_ja` | `.box-2 p[1]` stripped | Emoji marks removed with regex |
| `raw_title` | Same as `name_ja` | |
| `raw_description` | `開催日時: …\n放送: …\nジャンル: …\n{detail_text}` | See Date Extraction |
| `start_date` | Parsed from schedule string | See Date Parsing |
| `category` | Inferred from genre | See Category Mapping |
| `original_language` | `"ja"` | Always Japanese |
| `official_url` | `None` | Aggregator, not organiser |

## Date Parsing

Schedule format: `"4月29日 水曜 12:00　テレ東"` (full-width space before channel).

Regex: `(\d{1,2})月(\d{1,2})日\s+\S+?\s+(\d{1,2}):(\d{2})\s*(.+)`

**Year inference**:
- Start with `current_year`
- If resulting datetime is older than `LOOKBACK_DAYS` days, try `current_year + 1`
- This handles Dec→Jan boundary (upcoming January programs shown in December)

**Late-night convention** (`25:00` style): `hour >= 24` → subtract 24 hours and add 1 day.

Always prepend `開催日時: YYYY年MM月DD日\n` to `raw_description`.

## Taiwan Relevance Filter

| Keyword | Filter applied |
|---|---|
| `台湾` | None — all results are already Taiwan-relevant by definition |
| `テレサ・テン` | Only keep if full string `テレサ・テン` appears in title (blocks shows where テレサ is a minor guest, e.g. `昭和の名曲...明菜・テレサ・八代亜紀！`) |

## Category Mapping

| Gガイド Genre | Category |
|---|---|
| ドラマ | `performing_arts` |
| 映画 | `performing_arts` |
| 音楽 | `performing_arts` |
| ドキュメンタリー／教養, 報道 | `report` |
| バラエティ, スポーツ, other | `report` |

## Search Keywords

```python
SEARCH_KEYWORDS = ["台湾", "テレサ・テン"]
```

`台湾ドラマ` is a subset of `台湾` and returns the same results — no need to include.
`台湾特集` is optional; adds low volume and typically already matched by `台湾`.

## Lookback Window

`LOOKBACK_DAYS = 7` — skip programs that aired more than 7 days ago.
Upcoming broadcasts (future dates) are always included.

## Deduplication

1. **In-loop**: `seen_ebis_ids` set prevents same ebisId from being fetched twice across keyword searches.
2. **Safety net**: `dedup_events()` deduplicates by `(name_ja, start_date.date())`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `fetch_search_content` returns empty | Step 1 GET failed / no session cookie | Check if `resp1.raise_for_status()` passes; log cookie headers |
| `start_date` is in the wrong year | Year inference edge case | Check Dec→Jan rollover logic in `_parse_schedule` |
| Genre has extra whitespace (e.g. `バラ エティ`) | BeautifulSoup joining text nodes from HTML line breaks | Minor cosmetic issue; annotator handles it |
| テレサ・テン search returns J-pop variety show | `テレサ` appears without `・テン` in title | Already filtered — only full `テレサ・テン` passes |
| 0 results | Gガイド changed HTML structure | Re-inspect `ul.list-style-1 li.block` selector |
| Detail page returns empty `<main>` | Gガイド changed layout | Fall back to list-page title+schedule without description |

## Pending Rules

- Monitor whether `台湾特集` adds unique high-value results worth adding to `SEARCH_KEYWORDS`
- Consider adding `title-only` Taiwan filter for `台湾` keyword to reduce sports-broadcast false positives
