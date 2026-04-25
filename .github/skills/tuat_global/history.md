# TUAT Global Scraper — History

## 2026-04-26

**Implementation**: Initial build.

- Site uses WordPress with `/event/NNNNN/` URL pattern for post IDs.
- Listing page has all essential info (title, date, venue) in `<table>` elements — no need to fetch detail pages.
- Taiwan events identified by `（台湾）` in researcher affiliation within the title.
- Venue cell may contain multiple `<p>` elements (physical room + "Zoom") — take first for `location_name`, all non-http lines for `location_address`.
- Date format `"2026.4.15（14：00～15：30）"` uses full-width colon `：` for time separator.
- Scraper limits to 3 pages (30 events) with a 60-day lookback to avoid processing outdated entries.
