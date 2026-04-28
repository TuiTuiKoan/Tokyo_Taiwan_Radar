# K's Cinema Scraper — History

## 2026-04-29

**Added `official_url` extraction (defensive)** — same link-text pattern as `cinemart_shinjuku`.

### Key decisions

1. **Defensive only**: K's Cinema detail pages do not currently include a film official-site link. The extraction code is a no-op for now but future films may include one.

2. **All 3 Event() calls updated**: Parent event, sub-event (series), and single-film event all receive `official_url=official_url`.

3. **DB backfill not needed**: No current active events have an extractable official_url, so no manual DB update required.

---


**Initial implementation** — K's Cinema (`ks_cinema`) scraper created.

### Key design decisions

1. **Series vs. single film detection**: Use `len(film_h3s) >= 2` where `film_h3s` are `<h3>` elements inside the content div (immediate unnamed `<div>` after `div.head`). Filter out known sidebar h3 texts ("メニュー", "お問い合わせ" etc.).

2. **Date parsing bug fixed before commit**: First implementation used a two-pass approach (find all M/D patterns first, then find bare day numbers). This caused `4/25(土)・26(日)12:30` to attach `26` to the last-found month (May) instead of April, producing `end_date: 2026-05-26` instead of `2026-05-08`. Fixed by switching to a single left-to-right pass with a combined alternation regex (`M/D | SEP+bare_day`).

3. **Listing structure confirmed**: Both nowshowing and comingsoon list pages use `a[href*='/movie/']` with `<h2>` inside each `<a>`. The comingsoon page may be empty if no Taiwan films are upcoming — this is normal.

4. **Period table location**: The screening period (`上映期間`) is in the very last `<table>` in the HTML, which is wrapped in a `<div>` inside the content div.

5. **Source ID**: Positional index (`ks_cinema_{slug}_{0}`, `_{1}`, ...) chosen over title-based slug to avoid encoding issues with Japanese characters.

6. **Year inference**: `month < today.month - 3` threshold chosen to handle comingsoon films spanning the new year.

### Dry-run results

- Fetched 13 movie pages (nowshowing) — only 1 Taiwan page found: `taiwan-filmake`
- Generated: 1 parent event + 3 sub-events
- All dates, location, price_info confirmed correct
