# こくちーずプロ (Kokuchpro) Scraper History

## 2026-04-26 — Initial implementation

**Decisions made:**

- **Static HTML, no Playwright** — page renders fully server-side. `requests` + BeautifulSoup is sufficient. Run time is ~12 seconds for 70 events including detail page fetches.

- **Search URL scoped to 東京都** — `area-東京都` filter in the URL reduces noise significantly (226 Tokyo results vs 1102 nationwide). No additional geographic filtering in code needed.

- **ISO date from `.value-title[title]` attribute** — the card reliably carries an ISO 8601 datetime with JST offset (`+0900`). No need to parse Japanese date text on the listing page. Much more robust than text parsing.

- **hCard microformat for address** — the detail page embeds hCard (`fn org` for venue name, `adr` for address). This gives clean, structured address data without regex. `.adr` children joined with space produces `東京都 世田谷区三軒茶屋1-35-5`.

- **60-day cutoff for detail fetch** — fetching the detail page for every card (including old archived events) would be slow and unnecessary. Only events within 60 days past + all future events get a detail fetch. Older events use the card-level short description.

- **`REQUEST_DELAY = 0.4s`** — site has no explicit rate limit documented. 0.4s is conservative enough to avoid triggering any soft limits while keeping run time under 30 seconds.

- **Taiwan keyword guard on card data only** — applying the filter at card level avoids fetching detail pages for non-Taiwan events, which would waste quota and time.

- **`source_id` = URL slug** — Kokuchpro assigns each event either a platform-generated MD5 hash slug (e.g. `362e12f0b01d2f57ea3a517e60808a3a`) or an organizer-chosen short name (e.g. `tokyobonji0531`). Both are stable across runs — no timestamp or position-based IDs.
