---
name: ifi
description: Platform rules, date extraction, Taiwan filter, and troubleshooting for the 東京大学未来ビジョン研究センター (IFI) scraper
applyTo: scraper/sources/ifi.py
---

# IFI Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://ifi.u-tokyo.ac.jp` |
| List URL | `https://ifi.u-tokyo.ac.jp/event/` (upcoming) |
| Past events | `https://ifi.u-tokyo.ac.jp/old-event/` (46+ pages, not scraped) |
| Rendering | WordPress — static HTML, Playwright used |
| Auth required | No |
| Rate limit | 1 s sleep between detail pages |
| Source name | `ifi` |
| Source ID format | `ifi_{post_id}` (numeric WordPress post ID from `/event/{id}/`) |

## Platform Overview

IFI (Institute for Future Initiatives, The University of Tokyo) hosts academic seminars on sustainability, governance, and security. Taiwan-related events appear ~1–2 times per year, typically:
- Joint seminars with National Taiwan University (国立台湾大学)
- Taiwan-Japan comparative research workshops (offshore wind, supply chain, etc.)

**Upcoming events page shows very few events** (usually 1–5 at a time) — no pagination needed on `/event/`.

Past events (`/old-event/`) span 46+ pages with 9 cards each. Historical Taiwan events were found on pages 12, 15, 16, 21 (all pre-2025). The scraper only scans upcoming events — past events are not re-ingested.

## Page Structure

### List Page (`/event/`)

Cards: `ul.module_card-04 li`
- Link: `a[href*="/event/NNNN/"]`
- Title: `p.title`
- Venue preview: `p.venue`
- Date: `<time datetime="YYYY-MM-DD">`

No pagination on the upcoming events page.

### Detail Page (`/event/{id}/`)

Structured labels in `inner_text` format — label on one line, value on next:
```
日程：
2024年04月25日（木）
時間：
10:00-13:00
会場：
東京大学本郷キャンパス工学部一号館セミナーB (2階232)
https://... ← map link (filter out)
主催：
東京大学未来ビジョン研究センター ...
参加費：
無料
```

Title: `h1.module_title-01` or `h2.module_title-01`; fallback: last breadcrumb `<li> span`.

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `ifi_{post_id}` from `/event/{ID}/` |
| `raw_title` | `h1.module_title-01` / breadcrumb last span |
| `start_date` | `日程：` row + `時間：` row (start time) |
| `end_date` | Same as `start_date` (always single-day) |
| `location_name` | First non-URL line of `会場：` value |
| `location_address` | All non-URL lines of `会場：` value joined by `\n` |
| `is_paid` | `False` — IFI seminars are free (参加費：無料) |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + article.inner_text()` |
| `original_language` | `"ja"` (or `"en"` for English-title events) |

## Taiwan Relevance Filter

```python
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
```

Check card title first (fast reject). Re-verify on full detail page body.

0 Taiwan events = **expected and normal**. Taiwan events appear ~1–2 times per year.

## Date Parsing

`日程：` format: `"2024年04月25日（木）"` — always use `_parse_date(date_str, time_str)`.

`時間：` format: `"10:00-13:00"` — extract start time only.

Events are always single-day: `end_date = start_date`.

## Location Extraction Notes

`会場：` may include a map URL on the following line:
```
東京大学本郷キャンパス工学部一号館セミナーB (2階232)
https://www.u-tokyo.ac.jp/campusmap/...
```

**Always filter out lines starting with `http`** from the venue value before setting `location_name` / `location_address`.

Hybrid events may show two venue lines:
```
【オンライン】Zoomによるウェビナー
【対面】東京大学東洋文化研究所3F 大会議室
```
Use the first non-URL line as `location_name`; join all non-URL lines as `location_address`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events | No current Taiwan events | Expected — check upcoming event count |
| `start_date` null | `日程：` row absent | Check `_extract_info()` output |
| URL in `location_address` | Map link not filtered | Ensure HTTP-line filter is applied |
| Title returns `"イベント"` | `h1.module_title-01` fallback failing | Use breadcrumb span as fallback |

## Pending Rules

<!-- Added automatically by confirm-report -->
