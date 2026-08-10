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
| `location_url` | Official store/access page from the authoritative venue registry |
| `business_hours` | Event-specific schedule first; otherwise authoritative venue hours |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + main body text` |

## Price And Series Semantics

- `_extract_price_info()` accepts only an explicitly labelled event fee such as `参加費`, `料金`, or `入場料`.
- An unlabeled merchandise amount, menu price, workshop item price, or spend threshold for a prize draw is not the event admission price.
- When an umbrella page lists independently dated, located, or conditioned activities, model them as direct child events. Keep each child's own schedule and participation terms; do not flatten one product price or one nested time onto the parent.

## Venue Hours Ground Truth

- Official evidence: <https://www.eslitespectrum.jp/about/store/9cd1340f-26b6-4f55-9c33-d0487d7ac01d>
- General store hours: `平日 11:00～20:00、土日祝 10:00～20:00`.
- Persist these values in the authoritative `誠品生活日本橋` venue seed. If an event has no dedicated schedule, annotator may fill them from `venues.business_hours`.
- Event-specific schedules always win. The official page lists separate restaurant/tenant hours; never promote those exceptions to the general venue value.
- Labels such as `誠品生活日本橋 expo`, `誠品生活日本橋 書籍レジ`, and `誠品生活日本橋 各ショップ` keep their specific `location_name` while inheriting verified parent-venue metadata.

## Publication Rule Sync

- Pure publication classification is exact-only: normalized `event_form` must equal `['publication']`.
- Pure publication rows keep seven intentional-null fields with sentinel locks: `location_address`, `location_address_zh`, `location_address_en`, `business_hours`, `business_hours_zh`, `business_hours_en`, `location_prefectures`.
- Preserve real DB prices (`is_paid`, `price_info`, `price_amount`); hide pure-publication prices only in UI and JSON-LD. Price fields, `location_name`, and `location_url` are outside the seven-field NULL/clear policy.
- Publisher (`organizer`) stays required even for pure publication rows.
- Mixed physical rows (book launch/talk/signing/lecture/workshop) must not include `publication` in `event_form`.

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
