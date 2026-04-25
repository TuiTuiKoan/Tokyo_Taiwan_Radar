---
name: iwafu
description: Platform rules, Taiwan relevance gate, false-positive filters, and troubleshooting for the iwafu scraper
applyTo: scraper/sources/iwafu.py
---

# iwafu Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://www.iwafu.com` |
| Search URL | `https://www.iwafu.com/jp/events?keyword=台湾&prefecture=東京` |
| Rendering | JS-heavy — requires Playwright (`sync_playwright`) |
| Auth required | No |
| Rate limit | Implicit (no hard throttle; add 0.5 s between detail pages) |
| Source name | `iwafu` |
| Source ID format | `iwafu_{numeric_id}` (extracted from `/jp/events/{id}`) |

## Field Mappings

| Event Field | iwafu Source |
|-------------|--------------|
| `source_id` | `iwafu_{numeric_id}` from URL path (stable) |
| `raw_title` | `<h1>` on detail page |
| `start_date` | `_parse_date()` from card date range, confirmed on detail page |
| `end_date` | End of date range on card; falls back to `start_date` if single-day |
| `location_name` | `場所[：:]\s*(.+?)` from `main_text`; fallback: `card.prefecture` |
| `location_address` | Same value as `location_name` (set both) |
| `raw_description` | Detail page `main.inner_text()`, trimmed at first `_NOISE_MARKER` |

## Taiwan Relevance Gate

All events are fetched with `keyword=台湾` — iwafu applies the search server-side.
However a second relevance check is **mandatory** because iwafu search results can include:
- Global / nationwide tour events where Taiwan is merely one stop.
- IP entertainment series (escape rooms, anime tie-ins) that visit Taiwan venues.

### Global-tour false positive

Reject if description matches `_GLOBAL_TOUR_PATTERNS`:

```python
_GLOBAL_TOUR_PATTERNS = re.compile(
    r"台湾など世界各地|台湾など.*各地|全国各地.*台湾|世界各地.*台湾|台湾.*世界各地"
    r"|全国[0-9０-９]+[都道府県施設箇所].*台湾|台湾.*全国[0-9０-９]",
    re.DOTALL,
)
```

Taiwan must be the **theme or primary focus**, not just one venue.

### Title-level block (`_BLOCKED_TITLE_PATTERNS`)

Known IP series where all events are non-Taiwan-themed:

```python
_BLOCKED_TITLE_PATTERNS = re.compile(
    r"リアル脱出ゲーム.*名探偵コナン|名探偵コナン.*リアル脱出ゲーム"
    r"|名探偵コナン.*脱出|脱出.*名探偵コナン",
)
```

Check card title **before** loading the detail page (fast reject by card title, saves Playwright loads).

### Permanent series block (`_BLOCKED_SERIES`)

IP series where **every** event is confirmed non-Taiwan-themed. Checked on BOTH card title AND `<h1>` on detail page (card titles can be truncated).

```python
_BLOCKED_SERIES = re.compile(
    r"名探偵コナン",  # All Conan events — confirmed global-tour non-Taiwan-themed
)
```

Add new series entries here when an IP is confirmed.

## Location Extraction

- Primary: regex `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` on `main_text`.
- Set **both** `location_name` and `location_address` to the captured value.
- Fallback: `card.prefecture` (e.g. `"東京"`) — **only** when `場所：` label is absent.
- Never store bare prefecture names as `location_address` — they will be flagged by `backfill_locations.py`.

## Description Trimming

`_NOISE_MARKERS` defines UI section headers that signal the start of noise content.
Trim `raw_description` at the **first** occurrence of any marker (ordered list, first match wins):

```python
_NOISE_MARKERS = (
    "Q&A イベントについて",
    "近くの看板",
    "近くのイベント",
    "地図検索に切り替えて",
)
```

## DB Audit Rule

After adding a new filter (blocking pattern or series entry):
1. Run `ilike("raw_title", "%keyword%")` on the `events` table to find existing records.
2. Hard-delete or deactivate them — the filter only prevents future inserts.
3. Prefer hard-delete (`table.delete().eq("id", eid)`) for permanently non-Taiwan-themed series.

## Pending Rules

<!-- Added automatically by confirm-report -->
