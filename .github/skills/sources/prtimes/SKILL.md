---
name: prtimes
description: Platform rules, internal API discovery, Taiwan-vs-Japan filter, and date extraction for the prtimes scraper
applyTo: scraper/sources/prtimes.py
---

# PR TIMES Scraper — Platform Reference

PR TIMES (`prtimes.jp`) is Japan's largest press release distribution platform.
Taiwan-related event announcements are submitted by event organisers, venues, and
tourism/trade bodies and are a reliable early-warning source for upcoming Japan–Taiwan
cultural events.

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | https://prtimes.jp |
| API/Rendering | Internal JSON API (server-rendered detail pages) |
| Auth required | No — User-Agent header only |
| Rate limit | Not documented; 0.5 s polite delay is sufficient |
| Source name | `prtimes` |
| Source ID format | `prtimes_{release_id}` (e.g. `prtimes_68`) |

## API Discovery

The search endpoint was found by analysing the Next.js bundle
(`_app-d5e27ce51595715c.js`, module 20400):

```
G = `${$}/keyword_search.php`    where $ = "${location.origin}/api"
→ https://prtimes.jp/api/keyword_search.php
```

**Search endpoint:**
```
GET https://prtimes.jp/api/keyword_search.php/search
    ?keyword=<url-encoded>&page=<N>&limit=40
```

Response:
```json
{
  "data": {
    "current_page": 1,
    "last_page": 12,
    "limit": 40,
    "release_list": [
      {
        "release_id": 12345,
        "title": "...",
        "company_name": "...",
        "released_at": "2026年4月25日 17時00分",
        "release_url": "/main/html/rd/p/000012345.html"
      }
    ]
  }
}
```

Results are sorted **newest-first**. Maximum 250 pages × 40 = 10,000 results per keyword.

## Field Mappings

| Event Field | Source |
|-------------|--------|
| `source_id` | `prtimes_{release_id}` |
| `source_url` | `https://prtimes.jp` + `release_url` |
| `raw_title` | `title` from API response |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + detail-page body text (first 3000 chars) |
| `start_date` | Extracted from detail-page body (see Date Extraction) |
| `end_date` | Same as `start_date` (single-day default) |
| `location_name` | Extracted from `会場：` / `開催場所：` label in body |
| `location_address` | Same as `location_name` (not split further) |
| `original_language` | `"ja"` |

## Taiwan Relevance Filter

Two-stage title filter applied **before** fetching detail pages:

1. **Taiwan keyword**: `台湾|Taiwan|台灣|臺灣` must appear in title.
2. **Event-type keyword**: `イベント|フェス|開催|展示|祭|セミナー|講演|体験|交流会|…` must appear in title.

**Taiwan-based event exclusion** (applied after detail fetch):
- Title pattern `_TAIWAN_BASED_TITLE_RE`: matches `in 台湾`, `in Taiwan`, `台湾進出`, `台湾販路`, `台湾.*に集結` etc.
- Venue pattern `_TAIWAN_VENUE_RE`: venue contains 台北, 台中, 高雄, 新竹, 花蓮, Taipei, Kaohsiung etc.

Noise estimate: ~2.8% of results are Japan-held Taiwan events. The annotator
(`annotator.py`) acts as a second-pass filter.

## Date Extraction Notes

Priority order in `_extract_date_from_body()`:

1. **Labeled pattern** (highest confidence):  
   `開催日時：` / `日時：` / `開催日：` / `開催期間：` → extract `YYYY年MM月DD日 HH:MM` if present
2. **Year-less labeled pattern**:  
   `M月D日` after the label → inject year from `released_at`, advance 1 year if already past
3. **Standalone date scan**:  
   All `YYYY年MM月DD日` occurrences in body — skip index 0 (PR dateline), use first plausible candidate (not older than 2 years)
4. **Fallback**: `released_at` (PR publication date)

**Sanity check**: dates older than 2 years from now are rejected and replaced with `released_at`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 results for a keyword | API changed path | Check JS bundle for new `keyword_search` endpoint |
| `start_date` equals PR publish date | Labeled date pattern absent from detail page | Check HTML selector in `_fetch_detail`; body may be in different container |
| Taiwan-based events not filtered | Title pattern doesn't match | Add matching pattern to `_TAIWAN_BASED_TITLE_RE` or `_TAIWAN_VENUE_RE` |
| Duplicate events | Same PR submitted under multiple keywords | `seen_ids` set deduplicates by `release_id` within a run; Supabase upsert handles cross-run dedup |
| HTTP 429 / rate limit | Too many requests | Increase `_DELAY` (currently 0.5 s) |
| Detail page returns 404 | PR was deleted | `_fetch_detail` returns `("", "")` gracefully; `raw_description` falls back to title |

## Pending Rules

<!-- Added automatically by confirm-report -->
