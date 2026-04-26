---
name: cine_marine
description: Platform rules, listing structure, and Taiwan filter for the 横浜シネマリン scraper
applyTo: scraper/sources/cinemarine.py
---

# 横浜シネマリン Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://cinemarine.co.jp> |
| Rendering | Static HTML (WordPress) — no JS required |
| Auth | None |
| Rate limit | 0.3 s delay per film detail page fetch |
| Source name | `cine_marine` |
| Source ID format | `cine_marine_{slug}` (slug = URL path segment, e.g. `nittai`) |

## Listing Strategy

1. Fetch two listing pages: `/coming-soon/` and `/movie-now/`
2. Each listing page is a single long article with all film entries embedded
3. Walk `.entry-content` children: look for `<h2>` (date) + `<h3><a>` (title+URL) pairs
4. Apply Taiwan filter to the immediately following `<div class="content_block">` text
5. Deduplicate across listing pages by slug

## Listing Page HTML Structure

```html
<!-- end of previous film -->
<h2>6/27(土)～</h2>
<h3><a href="https://cinemarine.co.jp/nittai/">日泰食堂</a></h3>
<div class="content_block" id="custom_post_widget-87445">
  <p class="haikyu">2024年／台湾・香港・フランス／83分／...</p>
  <!-- description, credits, etc. -->
</div>
```

**Critical**: The sidebar of every film detail page lists all other current films with dates. Do NOT apply the Taiwan filter to the full film page text — only to the `content_block` in the listing page.

## Taiwan Relevance Filter

Applied only to `content_block` text (country/distributor line in `<p class="haikyu">`):

```
["台湾", "Taiwan", "臺灣", "金馬"]
```

False positive example: `花様年華` (Hong Kong only) should NOT match because its `haikyu` line reads `2000年／香港／98分` (no 台湾).

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `<a>` text inside `<h3>` |
| `raw_title` | same as `name_ja` |
| `source_id` | `cine_marine_{slug}` |
| `source_url` | film detail page URL |
| `start_date` | `<h2>` date text → parsed date |
| `end_date` | end of date range (if present) |
| `raw_description` | `.entry-content` of film detail page |
| `location_name` | `横浜シネマリン` (fixed) |
| `location_address` | `神奈川県横浜市中区花咲町1丁目1番地 横浜ニューテアトルビル` (fixed) |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Date Extraction

Date appears in `<h2>` element before each film entry.

Formats:
- `6/27(土)～` → start only (open-ended run)
- `4/25(土)－5/8(金)` → range with 全角ダッシュ (U+FF0D)
- `5/23(土)～6/5(金)` → range with 波ダッシュ

Regex: `r"(\d{1,2})/(\d{1,2})[^0-9\n]*?(?:－|〜|～|~)(\d{1,2})/(\d{1,2})"`

Year inference: `if month < today.month - 3 → assume next year`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 0 events found | Listing page structure changed | Inspect `<h2>` and `<h3>` pairing logic |
| False positives (Hong Kong films) | Taiwan filter applied to full page text | Ensure filter only checks `content_block` |
| `start_date` missing | `<h2>` text format changed | Add new date pattern to `_DATE_RANGE_RE` or `_DATE_START_RE` |
| Duplicate events | Both listing pages have same film | Deduplicated by slug (already handled) |

## Pending Rules

<!-- Add new rules discovered after initial implementation here -->
