---
name: hankyu_umeda
description: "Platform rules, HTML structure, and Taiwan relevance filter for the 阪急うめだ本店 scraper"
applyTo: scraper/sources/hankyu_umeda.py
---

# hankyu_umeda Scraper Skill

## Platform Profile

| Item | Value |
|------|-------|
| Site URL | https://www.hankyu-dept.co.jp/honten/event/ |
| API/Rendering | **static-html** — requests + BeautifulSoup (no Playwright needed) |
| Auth | None |
| Rate limit | Polite: `_DELAY = 0.5s` before each request |
| Source name | `hankyu_umeda` |
| Source ID format | `hankyu_umeda_{slug}` where slug = last path segment of detail URL; fallback `hankyu_umeda_{sha1(title+date_str)[:10]}` |

## HTML Structure (confirmed 2026-04-28)

```
article div.o-event[data-place="{code}"]
  └── a[href]                          # detail URL (may be external subdomain)
       └── p.o-event__title            # event title
       └── p.o-event__desc             # short description
  └── div.o-event__detail
       └── p  "◎4月22日（水）～27日（月）\n◎9階 催場"  # date + venue
Week header: p#week01, p#week02, … p#week05
```

## Field Mappings

| Event field | Source |
|-------------|--------|
| `raw_title` / `name_ja` | `p.o-event__title` |
| `raw_description` | `開催日時: …\n\n` + `p.o-event__desc` + detail text |
| `source_url` | `div.o-event > a[href]` (absolute URL) |
| `start_date` | `div.o-event__detail p:first` — `◎M月D日` regex |
| `end_date` | same — range after `～` |
| `location_name` | "阪急うめだ本店 " + 2nd `◎` line (e.g. "9階 催場") |
| `location_address` | hardcoded: "大阪府大阪市北区角田町8-7 阪急うめだ本店" |

## Taiwan Relevance Filter

`_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)`

Applied to BOTH `p.o-event__title` AND `p.o-event__desc`. Returns None if neither matches.

Past Taiwan event names (for testing):
- `台湾ライフ` (秋 年1回)
- URL slug: `taiwan_life`

## Date Extraction Rules

Date format: `◎4月22日（水）～27日（月）` (same-month) or `◎4月29日（水）～5月11日（月）` (cross-month)

Priority:
1. Cross-month regex `_DATE_DIFF_MONTH`: `◎(\d+)月(\d+)日…～(\d+)月(\d+)日`
2. Same-month regex `_DATE_SAME_MONTH`: `◎(\d+)月(\d+)日…～(\d+)日`
3. Single-day regex `_DATE_SINGLE`
4. Year inferred by `_infer_year()`: same year unless month < current month AND not in Dec→Jan wrap

## Key Rules

- Page shows **5 weeks** only. Taiwan展（台湾ライフ等）is typically in **autumn (September–November)**. During spring/summer the scraper returns 0 events — this is correct behavior.
- `source_id` uses the URL slug (`taiwan_life`) — stable across runs even if the page is re-scraped daily.
- No Playwright, no JS execution required.
- `location_address` is always hardcoded (Osaka, Kita-ku) — not extracted from page.
- `category` defaults to `["lifestyle_food"]`; annotator will refine.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 events in spring/summer | No Taiwan fair scheduled | Normal — check again in September |
| Date parse returns None | New date format variant | Add regex to `_parse_date_range()` |
| `source_id` changes between runs | URL not absolute (starts with `/`) | Check `_build_source_id` — ensure absolute URL passed |
| 65 items but 0 Taiwan | No current Taiwan event | Expected; re-run in autumn |

## Pending Rules

<!-- Add lessons learned from future debug sessions here -->
