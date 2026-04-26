# 台北駐大阪経済文化弁事処 Scraper — Implementation History

## 2026-04-26 — jposa_ja: initial implementation

**Context:** User requested a scraper for the Osaka TECO. The office's jurisdiction covers
Kansai + Chūbu + Hokuriku + Chūgoku + Shikoku (20 prefectures). Within the project's
all-Japan scope, this is a significant non-Tokyo source.

**Site structure discovery:**
- The main listing page `/jposa_ja/cat/4.html` is JavaScript-rendered; `requests` only returns
  the JS-gated skeleton (18 KB). However, the site is WordPress so RSS feeds exist.
- `/jposa_ja/rss_info.html` lists all category feeds.
- Relevant categories: 政務 (most cultural activity posts appear here), 文教 (academic/scholarship).
- WordPress REST API is disabled (404 on `/wp-json/`).
- RSS feeds paginate via `?paged=N` (10 items/page), sorted newest-first.

**Content analysis:**
- ~90% of posts are diplomatic visit recaps (「～の表敬訪問を受ける」).
- Cultural event posts: ~1–3 per month (film screenings, Taiwan festivals, seminars).
- The `content:encoded` in the RSS contains the full body HTML — no detail page fetch needed.
- Exception: if `content:encoded` is empty, fetch the detail page (static HTML, `requests` works).

**Event filter decisions:**
- `_EVENT_KW` — positive match on event-type words in title.
- `_SKIP_KW` — negative match on diplomatic visit patterns (title ends with 受ける/面会/歓迎).
- Combined, these reduce noise from ~90% → ~5% false positives.

**Date extraction:**
- Many recap posts (処長が XXXX に出席した) have the event date embedded in the title/body
  as a simple `4月11日` pattern. Year is inferred from the RSS pubDate.
- Full-year dates (2026年4月11日) appear in the body and are more reliable.
- Fallback to pubDate: accurate for same-day recap posts (office posts same day as event).

**source_id:**
- `jposa_ja_{post_id}` using the numeric ID from `/post/NNNNN.html`.
- The numeric ID is stable even if the title or slug changes.

**Lessons learned:**
1. Even JS-rendered listing pages often have WordPress RSS feeds — always check `/rss_info.html` before resorting to Playwright.
2. `XMLParsedAsHTMLWarning` must be suppressed when using BeautifulSoup's `html.parser` on RSS content.
3. For recap-style posts (処長が出席), the event date is the publish date ± 1 day; the body text usually contains the date explicitly.
4. Low yield (1–3 events/month) is expected and normal — do NOT increase `LOOKBACK_DAYS` beyond 180 unless event history backfill is needed.
