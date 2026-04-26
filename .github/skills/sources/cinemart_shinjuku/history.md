# Cinemart Shinjuku Scraper — History

## 2026-04-26

**Initial implementation** — `cinemart_shinjuku` scraper created.

### Key design decisions

1. **Asia-focused cinema**: Cinemart Shinjuku screens Korean, Chinese, and other Asian films — Taiwan keyword filter is mandatory. Keywords include `金馬` (Golden Horse Award) as a Taiwan-specific indicator beyond `台湾`/`Taiwan`.

2. **Listing link resolution**: Movie links on the listing page are relative 6-digit numbers (`002491.html`), not full paths. Resolved with `urljoin(_LISTING_URL, href)`. Pattern: `^\d{6}\.html$`.

3. **Two-pass filter**: Pre-filter on listing link text (cheap, avoids HTTP requests for non-Taiwan movies). Then full filter on detail page `<main>` text.

4. **Date parsing from first `<p>`**: The very first `<p>` inside `<main>` always contains the release date line (e.g. `5月8日(金)ロードショー`). Year inferred from today's date. `1日限定上映` → `end_date = start_date`.

5. **Sidebar stop words**: The detail page's `<main>` includes venue/sidebar info in `<dl>` elements after the film content. `<p>` collection is stopped when `_VENUE_STOP_WORDS` matches to avoid polluting `raw_description`.

6. **Source ID**: 6-digit movie number from URL (e.g. `cinemart_shinjuku_002491`) — stable across runs even if title changes.

### Dry-run results

- Fetched 36 movie pages (listing)
- Taiwan pre-filter passed: 2 movies
- Confirmed Taiwan movies:
  - `002491` 霧のごとく — start=2026-05-08, end=None (regular release)
  - `001840` 赤い糸 輪廻のひみつ — start=end=2026-05-28 (1日限定)
- All fields, dates, location confirmed correct
