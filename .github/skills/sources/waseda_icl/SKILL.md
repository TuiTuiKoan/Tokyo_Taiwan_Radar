---
name: waseda_icl
description: Platform rules, WP REST API date extraction, and Taiwan filter conventions for the waseda_icl scraper
applyTo: scraper/sources/waseda_icl.py
---

# Waseda ICL Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.waseda.jp/folaw/icl/news/` |
| API/Rendering | WordPress REST API (`/wp-json/wp/v2/posts?search=台湾`) |
| Auth required | No |
| Rate limit | None observed |
| Source name | `waseda_icl` |
| Source ID format | `waseda_icl_{wp_post_id}` (integer, stable) |

## Key Differences from waseda_taiwan.py

- **Different site**: `waseda.jp/folaw/icl/` (比較法研究所) vs `waseda-taiwan.com`
- **NOT Cloudflare-blocked**: ICL subdirectory allows WP REST API; main waseda.jp does not
- **Separate post IDs**: Events co-hosted with waseda-taiwan.com are posted on both sites with distinct WP post IDs — no source_id collision
- **Frequency**: ~1–2 events per year (legal symposia, Japanese-Taiwan law lectures)

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `waseda_icl_{wp_post_id}` |
| `start_date` | `【開催日時】` / `【日　時】` labels in post content |
| `location_name` | `【開催会場名】` / `【場　所】` labels in post content |
| `raw_description` | `"開催日時: YYYY年M月D日\n\n" + stripped post content` |
| `name_ja` | WP post title |

## Taiwan Relevance Filter

- **Two-stage**: WP API search (`search=台湾` + `search=Taiwan`) → title must also match `_TAIWAN_TITLE_RE`
- Title keywords: `台湾`, `日台`, `Taiwan`, `臺灣`
- **Skip 開催報告**: Posts with `【開催報告】` or `開催されました` in title are already-past events — always skip

## Date Extraction

- Labels inside `【】`: `【開催日時】`, `【日　時】` (with full-width space)
- `_extract_after_bracket_label()` stops at the next `【` or end of string
- **No year in some older posts**: infer from publication date if YYYY not found in content
- `LOOKBACK_DAYS = 120` — covers 4 months back

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events | No Taiwan events in current window (expected ~1–2/year) | Check manually at `/news/` — 0 is normal |
| `AttributeError` on date | Post has date label but malformed format | Add format to `_JAPANESE_DATE_RES` |
| Scraper not running | Not registered in `SCRAPERS` — see history | Run SCRAPERS audit |

## waseda_icl-specific Rules

1. **`_REPORT_RE` skip is critical**: Without it, all past events (事後報告 posts) would match. Always skip posts where title matches `【開催報告】` or `が開催されました`.
2. **WP API search is not exact match**: `search=台湾` also returns posts where 台湾 appears only in the body — hence the secondary `_TAIWAN_TITLE_RE` title-level filter.
3. **0 events is almost always correct**: This is a legal research institute; genuine Taiwan events occur ~1–2 times per year. Do not add more keywords to inflate results.
4. **`LOOKBACK_DAYS = 120`**: Longer than most scrapers because event announcements may be posted up to 3 months before the event date.
5. **No overlap with waseda_taiwan**: Different institutions; do not merge them via merger.py.

## Pending Rules

<!-- Add rules here as edge cases are discovered -->
