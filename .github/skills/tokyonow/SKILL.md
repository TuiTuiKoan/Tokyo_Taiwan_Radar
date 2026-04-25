---
name: tokyonow
description: Platform rules, API pagination, Taiwan keyword filter, and troubleshooting for the Tokyo Now scraper
applyTo: scraper/sources/tokyonow.py
---

# Tokyo Now Scraper — Platform Reference

## Platform Profile

| Field | Value |
|-------|-------|
| Site URL | `https://tokyonow.tokyo` |
| API base | `https://tokyonow.tokyo/wp-json/tribe/events/v1/events` |
| Rendering | WordPress + Tribe Events plugin — pure REST API, **no Playwright needed** |
| Auth required | No |
| Rate limit | 1 s sleep between pages (`_PAGE_DELAY = 1.0`) |
| Source name | `tokyonow` |
| Source ID format | `tokyonow_{numeric_id}` (WordPress post ID from `id` field — stable) |

## API Strategy

The Tribe Events v1 API supports keyword search via `search=台湾`, but the parameter returns **0 results** — it only searches event titles in English, not Japanese. Full-page scan with local filter is mandatory.

```
GET /wp-json/tribe/events/v1/events
  ?per_page=50
  &start_date=<YYYY-MM-DD>   ← today (JST)
  &page=<N>
```

Response includes:
- `total` — total event count
- `total_pages` — number of pages to iterate
- `events[]` — array of event objects

Fetch page 1 first to obtain `total_pages`, then paginate from page 2 onwards.

## Field Mappings

| Event Field | Tokyo Now API Source |
|-------------|----------------------|
| `source_id` | `tokyonow_{ev["id"]}` — numeric WordPress post ID (stable) |
| `source_url` | `ev["url"]` |
| `raw_title` | `_strip_html(ev["title"])` |
| `start_date` | `_parse_api_date(ev["start_date"])` — format `"YYYY-MM-DD HH:MM:SS"` JST |
| `end_date` | `_parse_api_date(ev["end_date"])`; fallback to `start_date` if None |
| `location_name` | `ev["venue"]["venue"]` (venue name) |
| `location_address` | `ev["venue"]["address"]` (full address string) |
| `is_paid` | `True` if `ev["cost"]` contains `¥`/`￥`/digits and no `無料`; `False` if `無料` or `"0"`; `True` if `ev["cost_details"]["values"]` non-empty |
| `price_info` | `ev["cost"]` stripped |
| `raw_description` | `"開催日時: YYYY年MM月DD日\n\n" + _strip_html(ev["description"])` |
| `original_language` | `"ja"` |

## Taiwan Relevance Filter

The API does NOT support server-side Japanese keyword search. Apply local filter after fetching each page:

```python
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
```

Check `title + " " + description` (after HTML strip). Return `None` from `_parse_event` if no match.

**Known false positive to avoid:** `台東区` (Tokyo ward). The current keyword list excludes `台東` and `台南` on purpose — use `台湾`/`Taiwan`/`臺灣` only.

## Date Parsing

API dates are JST strings in format `"2026-02-06 11:00:00"` (no timezone suffix). Parse as JST-aware:

```python
JST = timezone(timedelta(hours=9))
naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
return naive.replace(tzinfo=JST)
```

Never use `fromisoformat()` for these strings — Python's `fromisoformat` requires ISO 8601 with `T` separator.

## HTML Stripping

`ev["title"]` and `ev["description"]` contain raw HTML. Always strip before use:

```python
def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
```

## Raw Description Format

Always prepend the date prefix to `raw_description`:

```python
date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
if end_date and end_date.date() != start_date.date():
    date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
raw_description = date_prefix + "\n\n" + desc_text
```

## Expected Event Volume

- Total upcoming events (all categories): ~150–200 per day
- Taiwan-related events: typically **0–3** at any given time
- Scan time: ~5 s (4 pages × 50 events + 1 s page delay)

Dry-runs returning 0 events are **expected and correct** — it means no Taiwan events are currently listed. Do not treat 0 results as a scraper failure.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| 0 events, `total_pages=0` | API unreachable or 5xx | Check `resp.raise_for_status()`; retry |
| `total_pages=1` when expecting more | `start_date` too far in the future | Verify today's JST date |
| False positives with `台東` | Do NOT add `台東` to `_TAIWAN_KEYWORDS` | `台東区` is a Tokyo ward |
| `source_id` changes | Using title/position instead of `ev["id"]` | Always use the numeric WordPress post ID |
| `_parse_api_date` returns None | Date string format changed | Log the raw value; update strptime format |

## Pending Rules

<!-- Added automatically by confirm-report -->
