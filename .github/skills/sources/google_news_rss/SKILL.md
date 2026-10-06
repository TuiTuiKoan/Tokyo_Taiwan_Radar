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

- **依賴必須鎖版本**：`googlenewsdecoder==0.1.7` + `selectolax>=0.3,<1.0`（`requirements.txt`）。0.2.x 移除 `new_decoderv1`，selectolax 1.0 移除 `selectolax.parser`，任一升級都會在 import 階段讓整個 `main.py` 崩潰（2026-09-21 起停擺 15 天）。升級前先在乾淨 venv 驗證 `from googlenewsdecoder import new_decoderv1`。import 已有 guard：失敗時退回 Google News 轉址 URL 並記警告，不可移除這層保護。
- `source_id` uses the article URL (guid or link), so the same article across different queries deduplicates correctly via `dedup_events()`.
- 1.5s sleep between queries to avoid rate-limiting.
- Items older than 60 days (by pubDate) are silently skipped.
- `start_date` defaults to pubDate for news articles — the annotator is expected to refine it using the article body.
- Taiwan-only OTT/VOD launch news can still pass the Taiwan keyword filter. If the article is only about a Taiwan platform adding a title, with no Japan venue, participation path, or in-scope persistent value, the correct remediation is to deactivate the DB event (`is_active=false`) rather than trying to preserve it as a streaming event.
- Treat Taiwan-only OTT/VOD or news articles with no Japan event value as out-of-scope noise in the active pool: deactivate the DB event instead of preserving it.
- If the candidate pool for the same misfit class is under 20 active events, prefer a one-off DB patch or deactivation first. Do not introduce a new routine, backfill pipeline, or toolization before verifying that manual cleanup is insufficient.
