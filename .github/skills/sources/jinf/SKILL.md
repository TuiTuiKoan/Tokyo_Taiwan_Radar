---
name: jinf
description: Platform rules, meetingbox parsing, Taiwan filter, and registration link as source URL for the 国家基本問題研究所 (JINF) scraper
applyTo: scraper/sources/jinf.py
---

# JINF Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://jinf.jp/meeting |
| Type | Static HTML (single page) |
| Auth | None (public list) |
| Rate Limit | None observed |
| Source Name | `jinf` |
| Source ID Format | `jinf_{form_id}` (e.g. `jinf_226`) |
| `--source` key | `jinf` |

JINF (Japan Institute for National Fundamentals / 国家基本問題研究所) is a conservative think-tank in 千代田区平河町, Tokyo. It hosts public lectures and symposia on Japan's national interest, with occasional strong Taiwan-Japan relations focus.

## Listing Page Structure

Upcoming events are listed as `<div class="meetingbox">` elements:

```html
<div class="meetingbox " style="width:570px">
  <img src="..." alt="mtg">
  <p style="width:460px;">
    <strong class="title">EVENT TITLE</strong><br>
    【開催日】　 YYYY-MM-DD<br>
    【場　所】　 VENUE NAME<br>
    【登壇者】 　SPEAKERS...<br>
    <a href="/meeting/form?id=NNNN">【» 詳細／お申込みはこちら】</a>
  </p>
</div>
```

Note: `【場　所】` uses a full-width space (`　`) between 場 and 所.

## Taiwan Relevance Filter

Filter on **full box text** — Taiwan events appear via:
- Title substring: `日台関係`
- Speaker affiliation: `台湾元行政院副院長`, `台湾大学`
Keywords: `["台湾", "Taiwan", "臺灣"]`

## Field Mappings

| Event Field | Source |
|---|---|
| `name_ja` | `<strong class="title">` inner text |
| `start_date` | `【開催日】` value — format `YYYY-MM-DD`, midnight JST |
| `location_name` | `【場　所】` first non-http line |
| `source_url` | `https://jinf.jp/meeting/form?id=NNNN` |
| `source_id` | `jinf_{form_id}` from `/meeting/form?id=NNNN` |
| `is_paid` | `False` (public events) |
| `category` | `["geopolitics", "taiwan_japan"]` |
| `raw_description` | Date + venue + speakers block |

## Date Extraction

- Format: `YYYY-MM-DD` in `【開催日】` — no time given, use midnight JST
- `_parse_date()` uses `re.search(r'(\d{4})-(\d{2})-(\d{2})', ...)` to be robust

## Key Rules

1. **`source_id` = form ID**: Use `/meeting/form?id=NNNN` not the title hash — form IDs are stable across runs.
2. **`【場　所】` uses full-width space**: The label is `場　所` not `場所` — use both patterns in fallback.
3. **Single-page listing**: No pagination — all upcoming events on one page.
4. **Past events not scraped**: `/meeting` only shows upcoming events. Past events are in `/news/archives/` but use a different format — not scraped.
5. **Taiwan filter scope**: Filter on full box text, not just title — Taiwan may appear only in speaker affiliations.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| 0 events | No upcoming Taiwan events | Normal — check `/meeting` manually |
| venue parse fails | Label changed to `場所` (no space) | Already handled with fallback |
| `source_id` collision | JINF reused form ID | Check if event is actually different |

## Pending Rules

- Consider also scraping past events from `/news/archives/` if Taiwan-related meeting reports are desired (category: `report`).
