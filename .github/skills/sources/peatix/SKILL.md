---
name: peatix
description: Platform rules, field mappings, date extraction, and troubleshooting for the Peatix scraper
applyTo: scraper/sources/peatix.py
---

# Peatix Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Search URL | `https://peatix.com/search?q=<keyword>&l=JP-13` |
| Rendering | JS-heavy — requires Playwright (`sync_playwright`) |
| Auth required | No |
| Rate limit | 1.5 s sleep between detail page requests |
| Source name | `peatix` |

## Field Mappings

| Event Field | Peatix Source |
|-------------|---------------|
| `source_id` | MD5 hash of event URL (first 16 chars) |
| `raw_title` | Event page `<title>` or `<h1>` |
| `start_date` | `_extract_peatix_dates(page_text)` result |
| `end_date` | Same function; `None` if single-day |
| `business_hours` | `_extract_peatix_business_hours(page_text, date_text)` — time range (e.g., "14:00 - 15:30 GMT+09:00") |
| `location_name` | `_extract_peatix_location_from_text(page_text)` — venue name |
| `location_address` | Same function — street-level address (ward-only addresses rejected) |
| `raw_description` | Full body text with date prefix prepended |

## Date Extraction

- Primary: `_extract_peatix_dates(page_text)` — regex on full body text
- Format 1: `Mon, May 12, 2025` (English, typical)
- Format 2: `YYYY年MM月DD日` (Japanese fallback)
- CSS selectors used as fallback when regex returns nothing

### raw_description Convention

Prepend `開催日時: YYYY年MM月DD日\n\n` when `start_date` is known.

## Business Hours Extraction

**Function**: `_extract_peatix_business_hours(page_text: str, date_text: str | None = None) -> str | None`

**Supported Formats**:

1. **English block**: `DATE AND TIME\n\n...\n\n1:00 PM - 2:00 PM GMT+09:00`
2. **Japanese block**: `日時\n\nYYYY/M/D ...\n\n14:00 - 15:30 GMT+09:00`
3. **Body label**: `時　間｜14:00~15:30` or `時間：14:00-15:30`

**Fallback**: If no structured block found, extracts time range from `date_text` CSS selector result (if provided).

**Returns**: Time range string (e.g., `"14:00 - 15:30 GMT+09:00"`) or `None`.

## Price Extraction

Primary selector output comes from `.ticket-price` or `[class*='price']`. Treat selector values that are only generic labels (`料金`, `参加費`, `チケット`, etc.) as empty.

When selector output is empty or generic, fall back to body text only if the line starts with a known price label and contains a price/free signal:

- Labels: `参加費`, `料金`, `入場料`, `入場`, `チケット`, `費用`
- Signals: `無料`, `無償`, `円`, `¥`, `￥`, `JPY`
- Single amount: set `price_amount` to the integer value
- Multiple amounts or ranges: keep `price_info` text and leave `price_amount = None`

Never extract an unlabeled amount from body copy. It may be an item value, gift value, or unrelated number.

## Dedup

- Key: MD5 hash of event URL (first 16 chars)
- Maintain `seen_urls` set — initialized **once** per `scrape()` call, shared across all keyword loops

## Taiwan Relevance Gate

Body text must contain at least one `TAIWAN_KEYWORDS` entry.
**Never disable this gate.** Non-Taiwan events will pass the Tokyo filter and pollute the DB.

## Filtering Rules

| Rule | Implementation |
|------|----------------|
| Location | `l=JP-13` (Tokyo prefecture) in search URL |
| Date cutoff | Skip events older than 90 days; **keep** events with no `start_date` (annotator will handle) |
| Search limit | 20 pages per keyword |

## Chrome MCP (Local Dev Only)

When Peatix changes its page structure and selectors break:

1. Open Chrome, navigate to a Peatix event detail page.
2. Use `mcp_browser_snapshot` to capture the rendered DOM — Peatix is JS-rendered so static HTML differs.
3. Locate: `DATE AND TIME` heading, price section, venue block.
4. Update `_extract_peatix_dates()` and `_safe_text()` selectors in `peatix.py`.
5. **Never use Chrome MCP in CI** — production scraping always uses Playwright.

## Location Extraction

**Function**: `_extract_peatix_location_from_text(page_text: str) -> tuple[str | None, str | None]`

**Returns**: `(location_name, location_address)`

### Primary: Structured block regex (English & Japanese)

Peatix renders venues in a fixed 3-line block with **double blank lines** as structural separators:

- **English**: `LOCATION\n\n<venue>\n\n<address>\n\nJapan`
- **Japanese**: `場所\n\n<venue>\n\n<address>\n\nJapan`

**Online event detection**: If first line after `LOCATION` or `場所` matches online markers (`Online event`, `オンライン`, `ライブ配信`), returns `("オンライン", "オンライン")`.

**Address validation**: Ward-only addresses (e.g., `中央区`) without street-level detail (`丁目`, `番地`) are rejected → returns `(venue_name, None)`. Full addresses with street-level detail are accepted.

```python
# English block
loc_block_m = re.search(r'LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})', page_text)

# Japanese block
jp_loc_block_m = re.search(r'場所\n\n(.{3,100})\n\n([^\n]{3,200})', page_text)
```

### CSS fallbacks (when structured block absent)

```python
if not location_name:
    location_name = (
        _safe_text(page, ".venue-name")
        or _safe_text(page, "[class*='venue']")
    )
    # Do NOT use ".location" — it matches unrelated elements on the page
if not location_address:
    location_address = (
        _safe_text(page, ".venue-address")
        or _safe_text(page, "[class*='address']")
    )
```

### Address regex fallback

```python
if not location_address:
    addr_m = re.search(r'(?:〒\d{3}-\d{4}[^\n]*|東京都[^\s,，\n]{3,60})', page_text)
    if addr_m:
        location_address = addr_m.group(0).strip()
```

| Symptom | Cause | Fix |
|---------|-------|-----|
| `location_name` set to wrong venue (e.g. 赤坂) | `.location` CSS selector matching unrelated element | Remove `.location` selector; rely on structured block regex |
| `location_name`/`location_address` = `台南`/`台北` etc. | Structured block regex failed (single-newline bug), address fell through to annotation | Use double-newline regex (`LOCATION\n\n` or `場所\n\n`) |
| Missing `business_hours` for Japanese events | Only English `DATE AND TIME` block was extracted | Verify `_extract_peatix_business_hours()` includes `日時` block + body label patterns |
| `price_info` is only `料金` | Selector returned a label-only string | Treat generic price labels as empty and use high-confidence body price label fallback |
| All events missing `start_date` | Peatix changed date element markup | Use Chrome MCP to find new selector; update `_extract_peatix_dates()` |
| Events from outside Tokyo | `l=JP-13` ignored or URL changed | Verify search URL still includes `l=JP-13` |
| Duplicate events | `seen_urls` not shared across keyword loops | Ensure `seen_urls` is initialized once in `scrape()`, not per-keyword |
| Playwright timeout | JS render slower than usual | Increase `wait_for_load_state("networkidle")` timeout |
| Non-Taiwan events passing gate | `TAIWAN_KEYWORDS` too broad | Review keyword list; never remove the gate entirely |
| Cookie wall stored as event body | Pre-2026-06-28 events scraped before cookie guard added | Existing events need direct-URL one-off rescue (see below) — `upsert_events()` will not auto-fix due to idempotent skip |

## Cookie Wall Data Loss (Historical Issue)

**Timeline**: OneTrust cookie-consent wall became visible to Playwright in mid-2026. Events scraped between ~2026-06-15 and 2026-06-28 may have `raw_description` starting with `"About cookies on this site"` and null `business_hours`/`location_name`/`location_address`/`price_info`.

**Why `main.py --rescrape-ids` won't fix it**: `database.upsert_events()` skips existing non-force Peatix events by default (`if event_key in existing_keys and not force: continue`). The cookie guard (`_looks_like_cookie_banner()`) added in commit a62c3903 (2026-06-28) only prevents **new** writes — it does not trigger re-scraping of existing dirty rows.

**Correct repair path**: Use a **direct-URL one-off rescue script** (e.g., `scraper/_oneoff_rescue_peatix_cookies.py`) that:
1. Queries active Peatix events with `raw_description LIKE 'About cookies on this site%'`
2. Calls `PeatixScraper()._scrape_detail(page, source_url)` directly for each URL
3. Validates rescued event has non-cookie `raw_description` + complete fields (location/time/price)
4. Uses `upsert_events(..., force_keys={(source_name, source_id)})` to force-overwrite existing rows
5. Re-runs annotator **only on confirmed rescued UUIDs** (re-query after upsert to confirm)

**Never** rely on `--rescrape-ids` for cookie-wall repair — it will silently skip the row and report "0 events scraped" with no warning.
