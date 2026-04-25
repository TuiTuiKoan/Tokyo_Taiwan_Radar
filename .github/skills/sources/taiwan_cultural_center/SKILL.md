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

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Report articles have `start_date` = publish date | Tiers 1–3 all failed; fell through to Tier 4 | Inspect body text; check that Tier 1 label regex matches current markup |
| `start_date` off by one year | Year inference window too narrow | Verify −180 to +365 day window is applied around `post_date` |
| `end_date` null when `〜5日` present | End date parser not injecting year + month | Patch parser to carry over year + month from `start_date` |
| Parse error on `(土・祝)` | `strptime` receiving day-of-week suffix | Ensure `_parse_date()` strips all `（...）` / `(...)` groups first |
