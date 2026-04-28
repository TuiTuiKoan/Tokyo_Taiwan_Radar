---
name: google_news_rss
description: Platform rules, Taiwan filter, date extraction, and known quirks for the Google News RSS scraper
---

# google_news_rss Source

## Platform

Google News RSS search endpoint — returns up to ~10 articles per query, refreshed frequently.

Base URL: `https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja`

4 queries are fetched:
1. `台湾 展覧会 イベント 日本`
2. `台湾 フェスティバル 祭り`
3. `台湾映画 上映`
4. `台湾 講演 シンポジウム`

## Field Mappings

| Event field | Source |
|-------------|--------|
| `source_name` | `"google_news_rss"` |
| `source_id` | `gnews_{md5(article_url)[:12]}` |
| `source_url` | `<guid>` (if real URL) else `<link>` tag |
| `name_ja` | `<title>` text |
| `raw_title` | `<title>` text |
| `raw_description` | `"開催情報（Google News）:\n\n{description_plain}"` |
| `start_date` | Extracted from description; fallback to pubDate |
| `category` | `["report"]` — annotator refines |
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

## Article URL Extraction

Google RSS `<link>` tags are Google redirect URLs. Prefer `<guid>` when it starts with `http` and does not contain `news.google.com`. Otherwise use `<link>` as-is (no redirect following — keeps scraper fast).

## Known Quirks

- `source_id` uses the article URL (guid or link), so the same article across different queries deduplicates correctly via `dedup_events()`.
- 1.5s sleep between queries to avoid rate-limiting.
- Items older than 60 days (by pubDate) are silently skipped.
- `start_date` defaults to pubDate for news articles — the annotator is expected to refine it using the article body.
