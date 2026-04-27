# 台湾文化祭 (taiwanbunkasai.com) Scraper History

## 2026-04-26 — Initial implementation

**Decisions made:**

- **Static HTML, no Playwright** — page is fully server-rendered. `requests` + BeautifulSoup works. Total: 1 request.

- **Single-event site pattern** — unlike multi-event platforms, this site only ever shows 1 upcoming event at a time. After the event passes, the page is updated for the next one. The scraper always returns 0 or 1 events.

- **`source_id = taiwanbunkasai_{YYYY}_{MM:02d}`** — uses event year + month to ensure stability across runs and uniqueness across the ~3 annual events. The same event fetched repeatedly produces the same ID.

- **`out店概要` / `開催実績` block extraction** — the page has a clear heading structure. The event details live between these two headings. Extracting this block avoids including the contact form text and social links in `raw_description`.

- **Venue via `● 会場` label** — the page uses `●` bullets as section markers. `_VENUE_RE` captures the block after the venue bullet and strips trailing map/note text.

- **Zero-event gap is expected** — between events (after an event ends, before the next is announced), the page may temporarily show no date. `scrape()` returns `[]` in this case — this is correct behaviour, not a bug.

## 2026-04-26 — Fix: name_ja year suffix + venue map + merger priority

**Problem**: Initial implementation had `name_ja = page_title` ("台湾文化祭" without year), causing merger similarity vs iwafu = 0.71 (below 0.85 threshold). Merger would not fire, resulting in duplicate entries.

**Fixes applied**:

1. `name_ja` changed to `f"台湾文化祭{start_date.year}"` — matches iwafu naming pattern exactly (similarity = 1.000).
2. `official_url = HOMEPAGE_URL` added — propagates to primary after merger.
3. `_VENUE_MAP` added — resolves 中野 / KITTE keywords to canonical location_name + location_address instead of raw venue text.
4. `is_paid = False` added — 入場無料 verified on official site.
5. `merger.py SOURCE_PRIORITY["taiwanbunkasai"] = 7` — outranks iwafu (11); taiwanbunkasai becomes primary on merge.
6. `category = ["lifestyle_food", "performing_arts", "senses"]` added.

**Lesson**: For single-page official organiser sites, always construct `name_ja` with year suffix when aggregator sources (iwafu) append the year. Raw `<title>` tags often omit the year.
