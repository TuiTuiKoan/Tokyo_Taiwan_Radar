---
name: cinemart_shinjuku
description: Platform rules, page structure, and date extraction for the シネマート新宿 (Cinemart Shinjuku) scraper
applyTo: scraper/sources/cinemart_shinjuku.py
---

# Cinemart Shinjuku Scraper — Platform Profile

## Site Overview

| Field | Value |
|---|---|
| Site URL | https://www.cinemart.co.jp/theater/shinjuku/ |
| Tagline | アジアをもっと好きになる (Asia-focused) |
| Type | Static HTML — no JS rendering required |
| Auth | None |
| Rate Limit | `time.sleep(0.5)` between detail requests is sufficient |
| Source Name | `cinemart_shinjuku` |
| Source ID Format | `cinemart_shinjuku_{6-digit-number}` (e.g. `cinemart_shinjuku_002491`) |
| `--source` key | `cinemart_shinjuku` |

Cinemart Shinjuku (新宿文化ビル6F・7F) is an Asia-focused art cinema. It screens Korean, Chinese, and other Asian films in addition to Taiwan films — a **Taiwan keyword filter is always required**.

## Field Mappings

| Event Field | Source |
|---|---|
| `raw_title` | First `<h2>` in `<main>` |
| `start_date` | First `<p>` in `<main>`: `M月D日(曜)ロードショー` |
| `end_date` | `None` for regular releases; `= start_date` for `1日限定上映` |
| `location_name` | Fixed: `シネマート新宿` |
| `location_address` | Fixed: `東京都新宿区新宿3丁目13番3号 新宿文化ビル6F・7F` |
| `official_url` | First external `<a>` with link text matching `オフィシャルサイト` / `公式サイト` / `official site` in `<main>` |
| `is_paid` | Always `True` |
| `price_info` | `None` (no structured price on detail page) |
| `category` | `["movie"]` |
| `source_url` | Movie detail page URL |

## Page Structure

### Listing page (`/theater/shinjuku/movie/`)

```html
<a href="002491.html">  ← relative 6-digit link
  <h2>霧のごとく</h2>
  ... description text ...
</a>
```

- **Selector**: `a[href]` where href matches `^\d{6}\.html$`
- Resolve to full URL via `urljoin(_LISTING_URL, href)`
- Both nowshowing and past/upcoming movies appear on this single page

### Detail page (`/theater/shinjuku/movie/NNNNNN.html`)

```
<main>
  <p>5月8日(金)ロードショー</p>       ← FIRST <p> = release date
  <h2>霧のごとく</h2>                  ← Movie title
  <p>description...</p>
  <p>あらすじ content...</p>
  ...
  <h3>監督</h3>
  <h3>キャスト</h3>
  ...
  <dl>営業時間...</dl>                  ← SIDEBAR STARTS HERE — stop collecting
  <dl>劇場案内 新宿区新宿3丁目...</dl>
```

- Stop collecting `<p>` content when text contains `_VENUE_STOP_WORDS`
- Sidebar stop words: `"オープン時間"`, `"先売り指定席"`, `"次週タイムスケジュール"`, `"新宿区新宿3丁目"`, `"東京メトロ"`, `"詳しくはこちら"`

## Taiwan Relevance Filter

Keywords: `["台湾", "Taiwan", "臺灣", "金馬"]`

- **Fast pre-filter**: Check listing link text (cheap, no HTTP request)
- **Full filter**: Check entire `<main>` text on detail page

`金馬` (Golden Horse Award) is included as a Taiwan-specific indicator.

## Date Format and Parsing

First `<p>` in `<main>` contains the release date:

| Format | Parsed |
|--------|--------|
| `5月8日(金)ロードショー` | start=5/8, end=None (ongoing) |
| `5月28日（木）1日限定上映` | start=end=5/28 (single day) |
| `4月17日(金)より限定開催！` | start=4/17, end=None |

Year inference: `month < today.month - 3` → use `today.year + 1`.

## Source ID

Extract the 6-digit number from the URL:
- `https://...shinjuku/movie/002491.html` → `cinemart_shinjuku_002491`
- Numbers are stable — used as dedup key across runs

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `raw_description` includes sidebar info | `_VENUE_STOP_WORDS` not matching | Check actual sidebar `<p>` text; update stop words |
| No events despite Taiwan movies present | Taiwan keywords not in listing text | Check listing `<a>` text; add keyword to `_TAIWAN_KEYWORDS` |
| `start_date` is `None` | First `<p>` format changed | Check first `<p>` text on detail page; update regex in `_parse_release_date` |
| Listing returns 0 links | URL changed or `^\d{6}\.html$` pattern wrong | Check actual `<a href>` values on listing page |

## Pending Rules

_Add new lessons here after debugging sessions._
