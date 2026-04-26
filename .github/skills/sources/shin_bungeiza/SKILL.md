---
name: shin_bungeiza
description: Platform rules, Taiwan detection signals, and date parsing for the 新文芸坐 scraper
applyTo: scraper/sources/shin_bungeiza.py
---

# 新文芸坐 Scraper Skill

## Platform Profile

| Field | Value |
|---|---|
| Site URL | <https://www.shin-bungeiza.com/schedule> |
| Rendering | Static HTML — no JS required |
| Auth | None |
| Rate limit | Single-page scrape (no pagination) |
| Source name | `shin_bungeiza` |
| Source ID format | `shin_bungeiza_{slugified_title}` |

## Scraping Strategy

The schedule page has two content structures:

1. **`section.schedule-box-wrap`** — featured films with `<h1>` title and `<p class="schedule-date">` date range
2. **`div.schedule-content-txt` with `p.nihon-date`** — films in the daily schedule grid (no box-wrap wrapper)

Taiwan films often appear only in structure 2. Both must be scraped.

## Taiwan Relevance Filter (Three Signals)

Apply to **both** `schedule-box-wrap` sections and `nihon-date` paragraphs:

| Signal | Example | Reliability |
|---|---|---|
| `・台/` in `<small>` national code | `(2021・台/128分)` | Highest |
| Link href contains `taiwanfilm.net` | `<a href="https://taiwanfilm.net/…">` | High |
| Taiwan keywords in section text | `台湾`, `Taiwan`, `臺灣`, `金馬` | Medium |

## Date Extraction — `nihon-date` Structure

```html
<div class="schedule-content-txt">
  <p class="nihon-date"><a>タイトル</a><small>…・台/…</small></p>
  <h2><em>5/8</em>（金）</h2>   ← first h2: start date with M/D
  <div class="schedule-program">…</div>
  <h2><em>9</em>（土）</h2>     ← day-only (same month as first h2)
  …
  <h2><em>14</em>（木）</h2>   ← last h2: end day
</div>
```

**Critical**: Use `p.find_next("h2")` approach (iterate parent children after `p`) for start date — **not** `p.find_previous("h2")` which returns an h2 from a prior film block.

- **Start date**: first h2 after `p.nihon-date` in the same parent → parse `M/D` from `<em>` text
- **End date**: last h2 in same parent → parse day-only with start month; handle month wrap if `end_day < start_day`

## Field Mappings

| Event field | Source |
|---|---|
| `name_ja` | `<a>` text inside `p.nihon-date` (or `<h1>` for box-wrap) |
| `raw_title` | same as `name_ja` |
| `source_id` | `shin_bungeiza_{_slugify(title)}` |
| `source_url` | `https://www.shin-bungeiza.com/schedule` (fixed) |
| `start_date` | first h2 after nihon-date p |
| `end_date` | last h2 in same parent |
| `location_name` | `新文芸坐` (fixed) |
| `location_address` | `東京都豊島区東池袋1丁目43番5号` (fixed) |
| `category` | `["movie"]` |
| `is_paid` | `True` |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `start_date` is publish date (wrong) | Using `find_previous("h2")` instead of next | Iterate `parent.children` after `p` |
| `end_date == start_date` when there's a run | `end_h2_text` not matching day-only regex | Check `h2` format; update regex |
| 0 Taiwan films detected | `・台/` format changed on site | Inspect `<small>` tags; update signal |
| Warning for non-Taiwan film (KING OF PRISM) | Unrelated film has `schedule-box-wrap` with no date | Expected — warning is harmless |

## Pending Rules

<!-- Add source-specific lessons learned here -->
