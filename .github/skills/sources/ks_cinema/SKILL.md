---
name: ks_cinema
description: Platform rules, page structure, and date extraction for the K's Cinema (新宿K'sシネマ) scraper
applyTo: scraper/sources/ks_cinema.py
---

# K's Cinema Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://www.ks-cinema.com/movie/ |
| Type | Static HTML (WordPress) — no JS rendering required |
| Auth | None |
| Rate Limit | `time.sleep(0.5)` between requests is sufficient |
| Source Name | `ks_cinema` |
| Source ID Format | `ks_cinema_{url_slug}` (parent/single), `ks_cinema_{url_slug}_{N}` (sub-film) |
| `--source` key | `ks_cinema` |

K's Cinema (新宿K'sシネマ) is an art cinema in Shinjuku that screens various independent films — it is **NOT exclusively a Taiwan cinema**. A Taiwan keyword filter is always required.

## Field Mappings

| Event Field | Source |
|---|---|
| `raw_title` | `div.box-base > div.head > h1` (series/film title) |
| `start_date` | Last `<table>` containing `上映期間` row; `M/DD(曜)` parsed with year inference |
| `end_date` | Same table, end date from `M/DD(曜)～M/DD(曜)` range |
| `location_name` | Fixed: `K's cinema` |
| `location_address` | Fixed: `東京都新宿区新宿3丁目35-13 3F` |
| `is_paid` | Always `True` |
| `price_info` | `当日料金` row from period table |
| `category` | `["movie"]` |
| `source_url` | Movie detail page URL |

## Page Structure

### Listing pages

- URLs: `/movie/list/nowshowing/` and `/movie/list/comingsoon/`
- Selector: `a[href*='/movie/']` — exclude `/movie/list/` and bare `/movie/`
- Each `<a>` contains `<h2>` with the film title

### Detail page (`/movie/{slug}/`)

```
div.box-base
├── div.head
│   └── h1  (series or single-film title)
└── div  (no class — content div)
    ├── p, p, ...  (intro / series description)
    ├── h3         (sub-film 1 title)          ─┐
    │   ├── p      (schedule: '4/25(土)...')    │  repeated per sub-film
    │   ├── p, ... (description paragraphs)    │
    │   └── table  (監督/出演/作品情報 metadata) ─┘
    ├── h3         (sub-film 2 title)
    │   └── ...
    └── div        (screening period table wrapper)
        └── table  (上映期間 / 上映時間 / 当日料金 / 備考 rows)
```

- **Series detection**: content div has 2+ `<h3>` elements → create parent event + sub-events
- **Single film**: content div has 0-1 `<h3>` elements → one event
- **Period table**: `soup.select("table")[-1]` — the last `<table>` on the page has `上映期間`

## Taiwan Relevance Filter

Apply to `h1` title + full page text. Keywords: `["台湾", "Taiwan", "臺灣"]`

K's Cinema screens various genres — do NOT skip the filter.

## Date Format and Year Inference

Schedule format: `M/DD(曜)・DD(曜)HH:MM、M/DD(曜)～M/DD(曜)HH:MM`

Year inference rule:
- If `month < today.month - 3` → use `today.year + 1` (comingsoon spanning year boundary)
- Otherwise → use `today.year`

**Critical**: Parse schedule strings with a **single left-to-right pass** to attach bare day numbers to the most recently seen month. Two-pass approaches (find all M/D first, then find bare days) cause bugs where bare day `26` in `4/25・26` gets attached to the last-seen month (e.g., May) instead of April.

## Series vs. Single Film

- **Series** (`len(film_h3s) >= 2`): Create parent event + one sub-event per `<h3>`
  - Parent `source_id`: `ks_cinema_{slug}`
  - Sub-event `source_id`: `ks_cinema_{slug}_{idx}` (0-based positional index)
  - Sub-event `parent_event_id`: `ks_cinema_{slug}`
  - Sub-event dates from schedule `<p>` after each `<h3>`; fall back to overall period if schedule parse fails

- **Single film** (`len(film_h3s) < 2`): One event
  - `source_id`: `ks_cinema_{slug}`
  - Dates from period table

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `end_date` of sub-films shows wrong month | Two-pass date parsing: bare day attached to last-found month | Use single-pass `token_re` with alternation in `_parse_schedule_first_last` |
| `comingsoon` returns 0 links | No Taiwan films currently scheduled | Expected behavior — not a bug |
| `film_h3s` includes sidebar `<h3>` elements | `div.box-base` not found, fallback uses full `body` | Ensure `h1.find_parent("div", class_="box-base")` works; filter out known menu h3 text |
| Period table not found | Page has no `上映期間` table row | `overall_start/end` will be `None`; log warning |

## Pending Rules

_Add new lessons here after debugging sessions._
