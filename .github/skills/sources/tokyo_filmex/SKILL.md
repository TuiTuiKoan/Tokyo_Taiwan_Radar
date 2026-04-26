---
name: tokyo_filmex
description: Platform rules, listing structure, and Taiwan filter for the 東京フィルメックス scraper
applyTo: scraper/sources/tokyo_filmex.py
---

# 東京フィルメックス Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://filmex.jp> (NOT filmex.net — redirects to filmex.jp) |
| Rendering | Static HTML — no JS required (send Chrome User-Agent to avoid 403) |
| Auth | None |
| Rate limit | 0.3 s delay per film detail page fetch |
| Source name | `tokyo_filmex` |
| Source ID format | `tokyo_filmex_{year}_{cat}{num}` (e.g. `tokyo_filmex_2025_fc2`) |

## Program Categories

| Category code | Japanese name | URL |
|---|---|---|
| `fc` | フィルメックス・コンペティション | `/program/fc/` |
| `ss` | 特別招待作品 | `/program/ss/` |
| `mj` | メイド・イン・ジャパン | `/program/mj/` |

## Year Detection

- Fetch `/program/fc/` page title → extract first 4-digit year via regex
- Page title example: `"フィルメックス・コンペティション2025 - 第26回「東京フィルメックス」"`
- If `festival_year < today.year` → skip entirely (past festival, return `[]`)
- 2026 program is typically published around October each year

## Taiwan-Only Return Policy (CRITICAL)

**If `festival_year < today.year` → return `[]` immediately.**
This is intentional — we only want current/future festival events.
The scraper will activate automatically once 2026 program is published.

## Listing Page HTML Structure

```html
<div class="imgL_wrap02">
  <div class="textWrap areaLink">
    <p class="text01">女の子 / Girl</p>
    <!-- First bare <p> (no class) = country line -->
    <p>台湾 / 2025 / 125分 /
      監督：スー・チー（SHU Qi）
    </p>
    <p>Synopsis preview...</p>
    <ul class="nav03 type04">
      <li class="next"><a href="fc2.html">作品詳細をみる</a></li>
    </ul>
  </div>
</div>
```

**Taiwan filter**: country `<p>` (first bare `<p>`) must start with `"台湾"`

## Detail Page HTML Structure

```html
<!-- Screening dates in body text or structured list -->
11月23日（日）
15:20 -
朝日 (有楽町朝日ホール) ゲスト:...

11月27日（木）
18:35 -
HTC (ヒューマントラストシネマ有楽町)
```

## Venue Abbreviations

| Abbreviation | Full name |
|---|---|
| 朝日 | 有楽町朝日ホール |
| HTC | ヒューマントラストシネマ有楽町 |

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | listing `p.text01` — before ` / ` split (e.g. `"女の子"`) |
| `name_en` | listing `p.text01` — after ` / ` split (e.g. `"Girl"`) |
| `raw_title` | full `p.text01` text (e.g. `"女の子 / Girl"`) |
| `source_id` | `tokyo_filmex_{year}_{cat}{num}` |
| `source_url` | `https://filmex.jp/program/{cat}/{id}.html` |
| `start_date` | first screening date found in detail page body |
| `location_name` | venue from screening text (expanded from abbreviation) |
| `raw_description` | `開催日時: …\n\ncountry_line\n監督: …\n\nsynopsis` |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction Notes

- Screening text format: `"11月23日（日）"` → `_DATE_RE = r"(\d{1,2})月(\d{1,2})日（\w+）"`
- Combined with `festival_year` to form full date
- `raw_description` prefix: `開催日時: YYYY年MM月DD日\n\n`
- If no date found → return `None` (skip event)

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| 0 events returned | `festival_year < today.year` | Expected — 2026 program not yet published |
| 403 error | Missing User-Agent | Session headers include Chrome UA |
| Date parse fails | New screening format | Update `_DATE_RE` regex |
| Venue not recognized | New venue abbreviation | Add to `_VENUE_MAP` dict |
| `filmex.net` used | Old domain redirect | Always use `filmex.jp` |

## Pending Rules

- Monitor filmex.jp around October each year for 2026 program publication.
- If `/program/sp/` (プレイベント) ever has Taiwan films, add `"sp"` to `_CATEGORIES`.
