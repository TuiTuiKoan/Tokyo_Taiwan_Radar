---
name: nhk_rss
description: Platform rules, Taiwan filter, date extraction, and known quirks for the NHK RSS scraper
---

# nhk_rss Source

## Platform

NHK (Japan Broadcasting Corporation) public RSS news feeds — no authentication required.

Feeds fetched:
- `https://www3.nhk.or.jp/rss/news/cat4.xml` — international news
- `https://www3.nhk.or.jp/rss/news/cat7.xml` — culture/science

## Field Mappings

| Event field | Source |
|-------------|--------|
| `source_name` | `"nhk_rss"` |
| `source_id` | `nhk_{md5(item_link)[:12]}` |
| `source_url` | `<link>` tag (falls back to `<guid>`) |
| `name_ja` | `<title>` text |
| `raw_title` | `<title>` text |
| `raw_description` | `"NHKニュース:\n\n{description_plain}"` |
| `start_date` | Extracted from description; fallback to pubDate |
| `category` | `["report", "books_media"]` |
| `original_language` | `"ja"` |

## Taiwan Filter

```python
TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]
# Applied to: title + " " + description_plain_text
```

## Date Extraction Order

1. `YYYY年MM月DD日` in description
2. `YYYY/MM/DD` in description
3. `MM月DD日` in description → use pubDate year (adjust ±1 year for wrap)
4. Fallback: pubDate itself

## Known Quirks

- 0 events is a valid dry-run result — NHK covers Taiwan only when news events occur. Do not treat 0 as an error.
- NHK articles are news items, not structured event listings. `start_date` will almost always fall back to pubDate; the annotator should not be expected to extract a precise event start date.
- Items older than 90 days (by pubDate) are silently skipped.
- Each feed is wrapped in its own try/except — a single feed failure does not block the other.
