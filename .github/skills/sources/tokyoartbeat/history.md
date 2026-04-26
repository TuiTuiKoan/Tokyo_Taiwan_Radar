# tokyoartbeat — History

Newest at top.

---

## 2026-04-26 — Search API does not filter by keyword in headless Playwright

**Error**: Dry-run collected 42 candidate event URLs from `?query=台湾` but returned 0 Taiwan-related events.

**Root cause**: Tokyo Art Beat is a statically-exported Next.js app (`nextExport: true`). The `?query=台湾` parameter is processed entirely client-side by React. In headless Playwright:
1. The page renders default popular events (Daniel Buren, Urs Fischer, etc.)
2. `台湾` never appears in `page.inner_text("body")` — not even after 30s of waiting
3. Zero API responses from tokyoartbeat.com contain Taiwan content
4. The search button on `multipleSearch` is never enabled (blocked by cookie consent modal)
5. Cookie consent "OK" click does not enable the search button

**Confirmed behavior**:
- GA fires `view_search_results` with `search_term=台湾` — React processes the URL, but the API call to get filtered results never completes/renders
- The search results come from a Contentful/Hasura backend that requires logged-in session or specific tokens

**Fix**: Commented out `TokyoArtBeatScraper()` from `main.py` SCRAPERS list to avoid wasting CI time.

**Lesson**: For React/Next.js apps with static export, URL parameters may not be applied to search results in headless mode. The `networkidle` event fires before the filtered API response is received. Test by checking if the search keyword appears in `page.inner_text("body")` with a 30s `wait_for_function` timeout.

**Status**: Scraper is DISABLED. Needs a new approach:
- Option A: Intercept the actual Contentful/Hasura GraphQL query and call it directly
- Option B: Use a different data source for Tokyo art events with Taiwan content

---

## 2026-04-26 — Incorrect --source key

**Observation**: `--source tokyoartbeat` fails. Correct key: `tokyo_art_beat` (from `TokyoArtBeatScraper`).

**Lesson**: `--source` key = class name CamelCase → snake_case, minus `Scraper` suffix.
