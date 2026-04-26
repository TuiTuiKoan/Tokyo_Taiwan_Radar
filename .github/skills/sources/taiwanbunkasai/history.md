# 台湾文化祭 (taiwanbunkasai.com) Scraper History

## 2026-04-26 — Initial implementation

**Decisions made:**

- **Static HTML, no Playwright** — page is fully server-rendered. `requests` + BeautifulSoup works. Total: 1 request.

- **Single-event site pattern** — unlike multi-event platforms, this site only ever shows 1 upcoming event at a time. After the event passes, the page is updated for the next one. The scraper always returns 0 or 1 events.

- **`source_id = taiwanbunkasai_{YYYY}_{MM:02d}`** — uses event year + month to ensure stability across runs and uniqueness across the ~3 annual events. The same event fetched repeatedly produces the same ID.

- **`out店概要` / `開催実績` block extraction** — the page has a clear heading structure. The event details live between these two headings. Extracting this block avoids including the contact form text and social links in `raw_description`.

- **Venue via `● 会場` label** — the page uses `●` bullets as section markers. `_VENUE_RE` captures the block after the venue bullet and strips trailing map/note text.

- **Zero-event gap is expected** — between events (after an event ends, before the next is announced), the page may temporarily show no date. `scrape()` returns `[]` in this case — this is correct behaviour, not a bug.
