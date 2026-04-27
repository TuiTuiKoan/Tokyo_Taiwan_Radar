---
name: taipei-fukuoka
description: "Platform rules and field mappings for the 台北駐福岡経済文化弁事処 scraper"
applyTo: scraper/sources/taipei_fukuoka.py
---

# taipei_fukuoka — Platform Skill

## Platform Profile

| Property | Value |
|----------|-------|
| Source name | `taipei_fukuoka` |
| URL | `https://www.roc-taiwan.org/jpfuk_ja/` |
| Rendering | Static HTML (WordPress 4.3.5) |
| Coverage | 九州・中国地方（福岡・山口・熊本・鹿児島等） |
| Events/month | ~2-5件（季節変動あり） |

## Scraping Strategy

- Main page (`/jpfuk_ja/`) shows the latest **5** local posts
- Filter to `/jpfuk_ja/post/NNNN.html` only (skip external `taiwantoday.tw` links)
- Visit each post detail page and check for `日時：` / `開催日時：` in body
- Skip non-event posts (diplomatic visits don't contain date labels)

## Field Mappings

| Event field | Source |
|------------|--------|
| `name_ja` | `h2.fz-A` on detail page |
| `raw_title` | same as `name_ja` |
| `raw_description` | `開催日時: YYYY年MM月DD日\n\n{.page-content text}` |
| `start_date` | body regex `日時：...` → YYYY年MM月DD日; fallback: `MM月DD日` + `発信日時` year |
| `location_name` | body regex `場所[：:]...` or `会場[：:]...`; default: "九州・西日本" |
| `source_id` | `taipei_fukuoka_{post_id}` where post_id = numeric from `/post/NNNN.html` |
| `category` | `["taiwan_japan"]` (all events are Taiwan-Japan cultural) |

## Taiwan Filter

All posts are Taiwan-related by definition (Fukuoka branch of Taiwan's economic office).
The filter is for **event posts** (not diplomatic meeting reports):
- Keep: title contains `お知らせ` / `開催` / `シンポジウム` etc.
- Skip: posts without `日時:` in body AND without event keywords in title

## Date Extraction

| Pattern | Example |
|---------|---------|
| Full date in body | `日時：2026年4月25日（土）午前10時` → `2026-04-25` |
| Month-day in body (no year) | `日時：3月30日（月）15:00` → uses `発信日時：YYYY-MM-DD` year |
| Title date fallback | `4・25開催` / `4‧2防府市` → `YYYY-04-25` (uses pub year) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `start_date = null` for all events | Check if body regex `_DATE_LABEL_RE` matches; the label format may have changed |
| 0 posts | Main page structure changed; check if `.news-item` → `.text-holder` → `a[href*=/post/]` still works |
| Wrong events (diplomatic) | Tighten `_EVENT_TITLE_KEYWORDS` or add to `_EVENT_BODY_MARKERS` |
| Year mismatch | `発信日時：YYYY-MM-DD` pattern changed; fallback to `item["publish_date"][:4]` |
