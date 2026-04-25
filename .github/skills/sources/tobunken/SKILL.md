---
name: tobunken
description: Platform rules, keyword filter strategy, and date/venue extraction for the tobunken scraper (東京大学東洋文化研究所)
applyTo: scraper/sources/tobunken.py
---

# 東京大学東洋文化研究所 (Tobunken) Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://www.ioc.u-tokyo.ac.jp/seminar/index.php |
| Detail URL | `https://www.ioc.u-tokyo.ac.jp/news/news.php?id={id_param}` |
| API/Rendering | Static HTML — `requests` + BeautifulSoup, no Playwright needed |
| Auth required | No |
| Rate limit | None observed; add 0.3s sleep between detail fetches |
| Source name | `tobunken` |
| Source ID format | `tobunken_{id_param}` (e.g. `tobunken_MonJun91155522025`) |

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `tobunken_{id_param}` — `id` query param from detail URL |
| `source_url` | `https://www.ioc.u-tokyo.ac.jp/news/news.php?id={id_param}` (strip `\n` from href) |
| `name_ja` | `div#contentsbox h2` text |
| `start_date` | `当日期間：YYYYMMDD` footer (primary); `日時：YYYY年M月DD日` (fallback) |
| `location_name` | `場所：` or `会場：` label in `<p><strong>` block |
| `location_address` | Hardcoded `"東京都文京区本郷7-3-1 東京大学東洋文化研究所"` when venue contains `東洋文化研究所` |
| `raw_description` | `開催日時: YYYY年MM月DD日\n\n` + detail page body (stripped of footer metadata) |
| `category` | `["academic", "taiwan_japan"]` (annotator will refine) |
| `is_paid` | `False` (all seminars are free) |
| `original_language` | `"ja"` |

## Listing Page Structure

- URL: `https://www.ioc.u-tokyo.ac.jp/seminar/index.php`
- **No pagination** — all entries (~1534) are on a single page
- `<dl>` with paired `<dt>` (event date) and `<dd>` (title + link)
- DT format: `2026.04.20` (single day) or `2026.03.26 - 2026.03.27` (multi-day)
- DD format: `{title}（登録日：{internal_timestamp}）` — strip the `（登録日：...）` annotation
- Detail link: `/news/news.php?id={id_param}` — **relative path**, prepend `https://www.ioc.u-tokyo.ac.jp`
- Links have **trailing `\n`** in `href` attribute — always call `.strip()` on href

## Detail Page Structure

```html
<div id="contentsbox">
  <h2>{event title}</h2>
  <p><strong>日時：</strong>2025年7月11日（金）午後2時30分～午後5時</p>
  <p><strong>場所：</strong>東京大学東洋文化研究所３階第一会議室（対面のみ）</p>
  <p>...</p>
  <hr/>
  登録種別：研究会関連
  登録日時：MonJun911:55:522025
  ...
  当日期間：20250711 - 20250711
</div>
```

## Relevance Filter (Two-Tier)

All filtering is done at the **listing-page title level** before fetching detail pages.

### Tier 1 — Taiwan explicit

```python
["台湾", "Taiwan", "臺灣", "台湾史", "台湾海峡"]
```

### Tier 2 — Maritime / exchange / material history themes

```python
["海洋史", "交流史", "物質史", "海域", "南シナ海", "東シナ海",
 "海上", "海峡", "東南アジア", "琉球"]
```

Match if ANY keyword appears in the title. Taiwan is NOT required to be the primary topic — that is intentional.

**Expected yield**: ~3–5 events per 365-day window. `0` events is expected when no recent Taiwan/maritime seminars have been announced.

## Date Extraction Notes

**Primary**: `当日期間：YYYYMMDD` in the footer (always present, unambiguous format `20250711`)

**Fallback**: `日時：` label in `<p><strong>` block, then first `YYYY年M月DD日` pattern in body

**Do NOT use `掲載期間：`** (display period) as the event date — it precedes the actual event date.

## Venue Extraction Notes

**Label variants**: `場所：` (common), `会場：` (also used)

**Online suffix stripping**: Split on:
- `およびオンライン` / `及びオンライン` / `オンラインのみ`
- `& Zoom` / `＆ Zoom` / `& Teams` / `& Google Meet` (hybrid events)

**Post-split cleanup**: Remove orphaned `（` at end of string with `re.sub(r"[（(]\s*$", "", venue)`

**Location address**: When `location_name` contains `東洋文化研究所`, hardcode `location_address = "東京都文京区本郷7-3-1 東京大学東洋文化研究所"`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events scraped | No Taiwan/maritime seminars within 365-day window | Expected — wait for new announcements |
| `source_url` has `\n` | href from BeautifulSoup has trailing newline | Always `.strip()` href values |
| `location_name` truncated | Online suffix not matched (new platform name) | Add pattern to `re.split` in `_extract_venue` |
| Date from `日時` is wrong | Unusual format (全角digits, mixed) | Extend `_parse_detail_date` regex |
| Too many irrelevant events | Broad keyword (e.g. `海域`) matches non-maritime titles | Narrow keyword or add body-text secondary filter |

## Pending Rules

<!-- Added automatically by confirm-report -->
