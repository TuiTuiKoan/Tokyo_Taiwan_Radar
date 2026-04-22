---
name: date-extraction
description: "Authoritative rules for date extraction across all Tokyo Taiwan Radar scrapers — prevents null dates, wrong dates, and end_date omissions"
applyTo: "scraper/**"
---

# Date Extraction Rules

Canonical reference for all scraper date logic. Follow these rules in every scraper. Deviations are the root cause of the most common data quality bugs.

## The Single-Day Rule (most important)

```python
# After ALL date-extraction tiers, always enforce:
if start_date and end_date is None:
    end_date = start_date
```

**NEVER** leave `end_date = None` when `start_date` is known. Single-day events, lectures, screenings, and talks all have `end_date = start_date`.

## Tier Cascade (apply in order, stop at first success)

| Tier | Name | Example pattern | Function |
|------|------|----------------|---------|
| 1 | Body label (colon-inline) | `日時：2026年5月10日` | `_extract_event_dates_from_body()` |
| 1b | Body label (M.DD Day) | `日時：10.11 Sat 16:30` | `_extract_dotday_date_from_body()` |
| 1.3 | Prose date range | `11月28日〜12月14日` | `_extract_prose_date_range_from_body()` |
| 1.5 | Prose single date | `10月25日(土)に開催` | `_extract_prose_date_from_body()` |
| 2 | Title slash date | `3/17(火)` | `_extract_date_from_title()` |
| 3 | Publish date fallback | *(last resort)* | `start_date = post_date` |

When Tier 3 fires, still enforce the single-day rule: `end_date = post_date`.

## Supported Date Formats

| Format | Example | Handler |
|--------|---------|---------|
| `%Y/%m/%d` | `2026/05/10` | `_parse_date()` |
| `%Y.%m.%d` | `2026.05.10` | `_parse_date()` |
| `%Y-%m-%d` | `2026-05-10` | `_parse_date()` |
| `%Y年%m月%d日` | `2026年5月10日` | `_parse_date()` |
| `M.DD Day` | `10.11 Sat` | Tier 1b only |
| `%a, %b %d, %Y` | `Mon, May 12, 2025` | Peatix: `_parse_peatix_date()` |

## Day-of-Week Stripping

Before parsing, always strip bracketed day-of-week markers:

```python
raw = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
```

This handles `（月）`, `(火)`, `（土・祝）`, `（日）14:00` etc. Only strips brackets whose content starts with a **non-digit** — preserves `(2026)`.

## Year Inference

When year is absent (e.g. `10月25日(土)`):

- **Tier 1.5 / Tier 2**: accept if within **180 days before** `post_date` (covers recap articles)
- **Tier 1.3 / Tier 1b**: accept if within **365 days** of `post_date` (covers exhibitions with long ranges)
- Try `post_date.year`, then `post_date.year + 1`, then `post_date.year - 1`

## Abbreviated End Dates

End dates like `〜5日` or `〜3月5日` must have year+month injected from `start_date`:

```python
if not re.match(r'\d{4}', end_raw):
    if re.match(r'\d{1,2}月', end_raw):
        end_raw = f"{start.year}年{end_raw}"       # "3月5日" → "2026年3月5日"
    elif re.match(r'\d{1,2}日', end_raw):
        end_raw = f"{start.year}年{start.month}月{end_raw}"  # "5日" → "2026年5月5日"
```

## raw_description Date Prefix

Always prepend the extracted date to `raw_description` so the AI annotator always sees it:

```python
date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
if end_date and end_date != start_date:
    date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
date_prefix += "\n\n"
raw_description = date_prefix + (description_ja or "")
```

This is the **source of truth for the annotator**. If the prefix is wrong, the annotator writes wrong dates.

## Annotator Contract

The annotator (`annotator.py`) **must preserve scraper dates as a fallback**:

```python
"start_date": annotation.get("start_date") or event.get("start_date"),
"end_date": annotation.get("end_date") or event.get("end_date"),
```

GPT-4o-mini sometimes returns `null` for dates even when the event description clearly contains one. The scraper-extracted date (stored in the DB as `start_date`/`end_date`) must never be overwritten with `null`.

After setting from annotation + fallback, enforce once more:

```python
if update_data["start_date"] and not update_data["end_date"]:
    update_data["end_date"] = update_data["start_date"]
```

## Report / Recap Detection

When `raw_title` contains any of `レポート|レポ|報告|記録|アーカイブ|recap` (case-insensitive), auto-add `"report"` to `category`. The event date is the past event date, not the publish date.

## Peatix Date Extraction

Peatix renders dates in English:

```
DATE AND TIME
Mon, May 12, 2025
1:00 PM - 2:00 PM GMT+09:00
```

Or for archive/replay tickets:

```
DATE AND TIME
Fri, Apr 24, 2026 - Wed, Mar 31, 2027
```

The `_extract_peatix_dates()` function tries:
1. Range on one line (`Day, Mon DD, YYYY - Day, Mon DD, YYYY`)
2. Single date + time range on following line (`1:00 PM - 2:00 PM`)
3. Single date → same-day event, `start = end`

## Peatix Blocklist

Some events are scraped because `台北` appears only in a speaker bio or book title, not in the actual event content. Add these to `BLOCKED_TITLE_PATTERNS`:

```python
BLOCKED_TITLE_PATTERNS: frozenset[str] = frozenset([
    "Q-B-CONTINUED",
    "Soul Food Assassins",
])
```

Check against `name_ja` (the scraped original title, never overwritten). Return `None` from `_scrape_detail` if matched.

To add new false-positive series: add the series title stem to this frozenset.

## Known Edge Cases

| Site | Pattern | Solution |
|------|---------|---------|
| TCC | `10.11 Sat 16:30` in labeled section | Tier 1b: `_extract_dotday_date_from_body()` |
| TCC | `11月28日〜12月14日` with no label | Tier 1.3: `_extract_prose_date_range_from_body()` |
| Taioan | `■ 日時\n 2026年05月10日（日）\n 13:00～` | Tier 1 with newline-aware regex; strip trailing time `\d{1,2}:\d{2}.*` |
| Peatix | Replay tickets: `Apr 24, 2026 - May 31, 2026` | Range regex in Tier 1 of `_extract_peatix_dates()` |
| All | Publish date ≠ event date | Never use Tier 3 unless all other tiers fail |

## Adding a New Scraper

1. Import `_extract_event_dates_from_body`, `_extract_prose_date_range_from_body`, `_parse_date` from `taiwan_cultural_center`
2. Add any site-specific Tier 1 variant before calling the shared functions
3. Always end the cascade with: `if start_date and end_date is None: end_date = start_date`
4. Always set `raw_description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n" + body`
5. Dry-run and verify every scraped event has `start_date` populated and `end_date == start_date` for single-day events
