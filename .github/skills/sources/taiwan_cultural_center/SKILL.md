---
name: taiwan_cultural_center
description: Platform rules, 4-tier date extraction, report detection, and troubleshooting for the Taiwan Cultural Center scraper
applyTo: scraper/sources/taiwan_cultural_center.py
---

# Taiwan Cultural Center (TCC) — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Base URL | `https://www.tcc.go.jp/event/` |
| Rendering | Static HTML |
| Auth required | No |
| Source name | `taiwan_cultural_center` |

## Field Mappings

| Event Field | TCC Source |
|-------------|------------|
| `source_id` | MD5 hash of URL path (first 16 chars) |
| `raw_title` | `<h1>` or page title |
| `start_date` | 4-tier cascade (see below) |
| `end_date` | Same tier result; `None` if single-day |
| `location_address` | Fixed: `東京都港区虎ノ門1-1-12` |
| `raw_description` | Full body text with date prefix prepended |

## Date Extraction — 4-Tier Cascade

Apply in strict order. Fall through to the next tier only when the current tier returns no date.

| Tier | Method | Pattern |
|------|--------|---------|
| 1 | Body labels | `日時:` / `日 時:` / `会期:` / `開催日:` / `期間:` / `開催期間:` |
| 2 | Prose date | `MM月DD日(曜)` in body; year inferred from `post_date` (−180 to +365 day window) |
| 3 | Title slash | `M/DD(曜)` in title; year inferred from `post_date` |
| 4 | Publish fallback | `日付：YYYY-MM-DD` at page bottom — **use ONLY when tiers 1–3 all fail** |

### Month-Only Dates (Tier 1 extension)

- Pattern `期間：2026年5月～10月` contains month-only dates without day numbers.
- `_parse_date()` handles `YYYY年M月` → first day of that month (`day=1`).
- `_extract_event_dates_from_body()` advances month-only `end_raw` to the **last day** of the end month via `calendar.monthrange(y, m)[1]`.
- Commit reference: `039f532`

### Month-Only Dates (Tier 1 extension)

- Pattern `期間：2026年5月～10月` contains month-only dates without day numbers.
- `_parse_date()` handles `YYYY年M月` → first day of that month (`day=1`).
- `_extract_event_dates_from_body()` advances month-only `end_raw` to the **last day** of the end month via `calendar.monthrange(y, m)[1]`.
- Commit reference: `039f532`

### Critical Parsing Rules

- `_parse_date()` must strip parenthetical day-of-week markers `（月）` / `(土・祝)` before `strptime`
- End dates with only a day number (`〜5日`): inject year + month from `start_date`
- **Never overwrite** `raw_title` or `raw_description` with translated or processed content

### raw_description Convention

Prepend `開催日時: YYYY年MM月DD日\n\n` when event date ≠ `post_date`.

## Report Detection

Auto-add `"report"` to category when title contains:

```
レポート|レポ|報告|記録|アーカイブ|recap
```

## Dedup

- Key: MD5 hash of URL path (first 16 chars)

## Chrome MCP (Local Dev Only)

When selectors break or a new page structure appears:

1. Open Chrome DevTools, navigate to a TCC event page.
2. Use `mcp_browser_snapshot` to capture the accessibility tree.
3. Look for: `.list-text.detail` body container, date label pattern, `日付：` publish date element.
4. Update `taiwan_cultural_center.py` with corrected selectors.
5. **Never use Chrome MCP in CI** — production scraping always uses Playwright.

## 連続上映企画 (Series Screenings)

For annual film screening series (e.g. 台湾映画上映会), the event page lists all individual screenings in a long description (10+ films, 13,000+ chars). **Do NOT rely on GPT annotation to generate sub-events** from this description — GPT-4o-mini reliably extracts only the first 2 entries even with 20,000-char input limit.

**Recommended approach:**
1. In the scraper, parse each screening entry (title, date, time, venue) from the page body.
2. Emit each screening as a separate `Event` with `parent_event_id` pointing to the series parent.
3. Set `source_id = f"{parent_source_id}_sub{n}"` for each screening.

**2026 映画上映会 reference:**
- 16 sub-events manually inserted 2026-04-29 (commit `603d7c4` history); see `taiwan_cultural_center/history.md`.
- Pattern: `『{title}』\n{M月D日(曜) HH:MM開演}／{venue}`.

## 連続上映企画 (Series Screenings)

For annual film screening series (e.g. 台湾映画上映会), the event page lists all individual screenings in a long description (10+ films, 13,000+ chars). **Do NOT rely on GPT annotation to generate sub-events** from this description — GPT-4o-mini reliably extracts only the first 2 entries even with a 20,000-char input limit.

**Recommended approach:**
1. In the scraper, parse each screening entry (title, date, time, venue) from the page body.
2. Emit each screening as a separate `Event` with `parent_event_id` pointing to the series parent.
3. Set `source_id = f"{parent_source_id}_sub{n}"` for each screening.

**2026 映画上映会 reference:**
- 16 sub-events manually inserted 2026-04-29; see `taiwan_cultural_center/history.md`.
- Screening entry pattern: `『{title}』\n{M月D日(曜) HH:MM開演}／{venue}`.
- **Always extract `name_zh` from `原題：` line** in the description. Do NOT guess or translate from Japanese.
- **`source_url` for sub-events = parent's `source_url`** — never use a guessed URL.
- **After inserting sub-events, update parent `start_date`/`end_date`** to `MIN(sub.start_date)` / `MAX(sub.end_date)`.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Report articles have `start_date` = publish date | Tiers 1–3 all failed; fell through to Tier 4 | Inspect body text; check that Tier 1 label regex matches current markup |
| `start_date` off by one year | Year inference window too narrow | Verify −180 to +365 day window is applied around `post_date` |
| `end_date` null when `〜5日` present | End date parser not injecting year + month | Patch parser to carry over year + month from `start_date` |
| Parse error on `(土・祝)` | `strptime` receiving day-of-week suffix | Ensure `_parse_date()` strips all `（...）` / `(...)` groups first |
| `start_date` = publish date for `期間：2026年5月～10月` | `_parse_date()` didn’t handle month-only `YYYY年M月` format | Add `YYYY年M月` → `day=1` case; advance end-date to last day via `calendar.monthrange` |
| sub-events only 2 of 16 for film series | GPT truncates sub-event output for long descriptions | Parse screenings in scraper layer; emit each as `Event(parent_event_id=…)` |
| `start_date` = page publish date when period is `2026年5月～10月` | `_parse_date()` didn't handle month-only format | Ensure `YYYY年M月` → `day=1` case exists in `_parse_date()`; end_date → last day of end month via `calendar.monthrange` |
| sub-events only 2/16 for film series | GPT truncates sub-event output for long descriptions | Parse screenings in scraper layer; emit each as `Event` with `parent_event_id` |
