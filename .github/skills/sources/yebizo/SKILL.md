---
name: yebizo
description: "Platform rules and Taiwan filter for the 恵比寿映像祭 scraper"
applyTo: scraper/sources/yebizo.py
---

# yebizo — Platform Skill

## Platform Profile

| Property | Value |
|----------|-------|
| Source name | `yebizo` |
| URL | `https://www.yebizo.com/jp/archives/program` |
| Rendering | Static HTML (WordPress) |
| Coverage | 東京・恵比寿（年1回・主に2月） |
| Events/year | ~3-10件（台湾関連のみ） |

## Key Characteristics

- Annual festival held at 東京都写真美術館 (TOP Museum)
- 2026 edition has strong Taiwan connection: curators 邱于瑄, 侯怡亭; artist 張恩滿
- Taiwan relevance varies by year — NOT every edition is Taiwan-related
- Program listing at `/jp/archives/program` shows all ~67 programs for the current edition
- Off-season (March–November): scraper returns 0 events (acceptable)

## Scraping Strategy

1. Fetch `/jp/archives/program` → parse all `<a href="/jp/program/NNNN">` links
2. **Pre-filter** on listing page: artist has CJK+katakana name pattern (e.g. 張恩滿（チャン・エンマン）) OR link text contains 台湾/台灣
3. **Confirm** by fetching each candidate's detail page → check `<p>` text for `台[湾灣]`
4. Create one Event per confirmed Taiwan-related program

## Link Text Format

```
type|[subtype]|price|title/artist|date[|time_range]|venue[|artist_repeat]
```

Examples:
- `展示|無料|張恩滿（チャン・エンマン）|2026年2月6日 - 2026年2月23日|東京都写真美術館 B1F 展示室`
- `ライヴ・イヴェント|ワークショップ|有料|針と糸と料理...|2026年2月7日|11:00 - 12:30|東京都写真美術館 1F スタジオ`

Note: When a time range segment follows the date, skip it when extracting the venue.

## Field Mappings

| Event field | Source |
|------------|--------|
| `name_ja` | `h1.single_article__ttl` on detail page |
| `raw_title` | same |
| `raw_description` | `開催日時: ...\n\n` + `<p>` text from `<main>` |
| `start_date` | First `_DATE_RE` match in listing link text |
| `end_date` | Second `_DATE_RE` match (if range) |
| `location_name` | First non-date/non-time segment after date in link text |
| `location_address` | Hardcoded: `東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内` |
| `is_paid` | `有料` / `無料` in link text |
| `source_id` | `yebizo_{program_id}` where program_id = numeric from `/jp/program/NNNN` |
| `category` | `["art"]` |

## Taiwan Pre-filter Pattern

```python
# Foreign East Asian artist: 2+ CJK chars + katakana reading in （）
_FOREIGN_ARTIST_RE = re.compile(r'[\u4e00-\u9fff]{2,}（[ァ-ヴ・ー]{3,}）')
# Taiwan keywords in listing or detail text
_TAIWAN_RE = re.compile(r'台[湾灣]|台湾原住民|台灣|タイワン')
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 0 programs found | Check if `/jp/archives/program` URL still works; structure may change yearly |
| 0 candidates after pre-filter | Festival theme changed — no Taiwan artists; expected behavior in off-Taiwan years |
| Wrong venue | Time segment `\d{1,2}:\d{2}` immediately after date must be skipped by `_TIME_RE` |
| `h1.single_article__ttl` missing | Fall back to `artist` extracted from listing link text |
| Detail page returns 403/rate-limit | Increase `time.sleep(0.8)` in scraper loop |
