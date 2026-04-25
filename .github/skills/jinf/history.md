# JINF Scraper — History

## 2026-04-26

**Implementation**: Initial build.

- `/event` and `/lecture` URLs return 404 — the correct page is `/meeting`.
- Upcoming events are in `<div class="meetingbox">` elements, not articles or list items.
- Event title is in `<strong class="title">` — do NOT use `<h3>` or `<h2>` (those are section headers).
- `【場　所】` uses a full-width space (U+3000) between 場 and 所 — regex must account for this.
- Registration link `/meeting/form?id=NNNN` is used as `source_url` and provides a stable `source_id`.
- Taiwan filter on full box text catches speaker affiliations (`台湾元行政院副院長`) not just the title.
- `_extract_field()` regex stops at next `【` delimiter — correct for multi-field extraction.
