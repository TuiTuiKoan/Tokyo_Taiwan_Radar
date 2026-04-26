---
name: eslite_spectrum
description: Platform rules and field mappings for the 誠品生活日本橋 (eslite spectrum Nihonbashi) scraper
---

# eslite_spectrum — Source Skill

## Platform Overview

- **Name**: 誠品生活日本橋 (eslite spectrum Nihonbashi)
- **URL**: <https://www.eslitespectrum.jp/news>
- **Type**: Taiwanese cultural bookstore and event space in Tokyo
- **Location**: COREDO室町テラス 2F, 東京都中央区日本橋室町3-2-1
- **Rendering**: Static HTML (requests + BeautifulSoup)
- **Events/month**: ~2–4 Taiwan-related events

## Scraper Key

```
--source eslite_spectrum
```

Class: `EsliteSpectrumScraper` → key auto-derived as `eslite_spectrum` (matches `SOURCE_NAME`).

## Strategy

1. Fetch `/news` listing page (static HTML).
2. Collect all `/news/catalog/{id}` links with published date and title.
3. For each item, fetch the detail page.
4. Filter: check Taiwan keywords against `content_text = f"{title}\n{description}"` only (NOT the full page HTML).
5. Extract event date from the detail page body (first `YYYY-MM-DD` string).

## Field Mappings

| Field | Source |
|-------|--------|
| `source_id` | `eslite_spectrum_{catalog_id}` (e.g. `/news/catalog/9` → `eslite_spectrum_9`) |
| `source_url` | `https://www.eslitespectrum.jp/news/catalog/{id}` |
| `name_ja` | Article `<h1>` or equivalent title element |
| `start_date` | First `YYYY-MM-DD` string found in detail page body |
| `location_name` | Always `"誠品生活日本橋"` (hardcoded) |
| `location_address` | Always `"東京都中央区日本橋室町3-2-1 COREDO室町テラス2F"` (hardcoded) |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + main body text` |

## Taiwan Filter Rules

**IMPORTANT**: Keywords are checked against main content only:

```python
content_text = f"{title}\n{description}"
```

Do NOT check `page.text` or the full HTML — `誠品` appears in every page's navigation and footer, which would cause all articles to match.

### TAIWAN_KEYWORDS

```python
["台湾", "Taiwan", "臺灣", "台灣", "台北", "高雄", "台中", "台南", "台日", "日台"]
```

Note: `"誠品"` is intentionally excluded — it appears in every page's nav/footer.

### Skip patterns (`_SKIP_TITLE_RE`)

Articles with these title patterns are skipped before detail-page fetch:

```
会員募集 | メンバーズカード | ワークショップカレンダー | ポイント | お知らせ | 営業時間 | 定休日 | リニューアル
```

## Date Format

Detail pages contain dates in `YYYY-MM-DD` format embedded in the body text.
Example: `2026-06-07` extracted from `【開催日時】2026年6月7日`.

The scraper uses `_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")` to extract the first match.

## Known Issues / Edge Cases

- The site has very few news items at a time (~5 per listing page). No pagination needed.
- Some items are glass workshop calendars (non-Taiwan). `_SKIP_TITLE_RE` filters these.
- Catalog IDs are sequential integers; IDs may be reused if articles are deleted.
