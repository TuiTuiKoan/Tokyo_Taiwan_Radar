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
| `location_name` | Venue block on detail page |
| `raw_description` | Full body text with date prefix prepended |

## Date Extraction

- Primary: `_extract_peatix_dates(page_text)` — regex on full body text
- Format 1: `Mon, May 12, 2025` (English, typical)
- Format 2: `YYYY年MM月DD日` (Japanese fallback)
- CSS selectors used as fallback when regex returns nothing

### raw_description Convention

Prepend `開催日時: YYYY年MM月DD日\n\n` when `start_date` is known.

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

### Primary: LOCATION block regex
Peatix renders venues in a fixed 3-line block: `LOCATION\n\n<venue>\n\n<address>`.
The **double blank line** is structural — a single-newline regex captures empty string.

```python
loc_block_m = re.search(r'LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})', page_text)
if loc_block_m:
    location_name = loc_block_m.group(1).strip()
    addr_candidate = loc_block_m.group(2).strip()
    if addr_candidate.lower() not in ('japan', 'online', 'オンライン'):
        location_address = addr_candidate
```

### CSS fallbacks (when LOCATION block absent)
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
| `location_name` set to wrong venue (e.g. 赤坂) | `.location` CSS selector matching unrelated element | Remove `.location` selector; rely on LOCATION block regex |
| `location_name`/`location_address` = `台南`/`台北` etc. | LOCATION regex failed (single-newline bug), address fell through to annotation | Use `LOCATION\n\n` double-newline regex |
| All events missing `start_date` | Peatix changed date element markup | Use Chrome MCP to find new selector; update `_extract_peatix_dates()` |
| Events from outside Tokyo | `l=JP-13` ignored or URL changed | Verify search URL still includes `l=JP-13` |
| Duplicate events | `seen_urls` not shared across keyword loops | Ensure `seen_urls` is initialized once in `scrape()`, not per-keyword |
| Playwright timeout | JS render slower than usual | Increase `wait_for_load_state("networkidle")` timeout |
| Non-Taiwan events passing gate | `TAIWAN_KEYWORDS` too broad | Review keyword list; never remove the gate entirely |
